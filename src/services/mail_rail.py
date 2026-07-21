"""
Reference PostgreSQL mail rail used by Digital Secretariat.

Two client-facing send verbs, both riding on the audited SMTP gateway
(src/services/smtp_gateway.py — every attempt lands in email_send_log):

  send_template(...)        — autonomous sends from a pre-approved template
                              registry (email-templates/rail/*.md, YAML
                              frontmatter + Jinja2 Polish body). Guards INSIDE
                              the call: atomic idempotency (mail_rail_sends),
                              per-company kill-switch (mail_rail_optouts),
                              optional cooldown_days.

  create_curated_draft(...) — one-off mail queued in email_drafts as
                              pending_approval; an optional operator notifier
                              releases/rejects by reply (wave-2 poller calls
                              release_draft/reject_draft).

DB access is direct psycopg2 (this IS the plumbing layer; connection pattern
copied from scripts/daily_invoice_processor.py). Every client email goes
through smtp_gateway.send_email — zero raw smtplib here.

Kill-switch: mail_rail_optouts(company_id, category) — category '*' opts a
company out of ALL rail mail. Generalizes the obligation-specific
companies.connector_auto_questions boolean (see send_obligation_questions.py).

Idempotency contract: the INSERT ... ON CONFLICT DO NOTHING into
mail_rail_sends is the atomic guard (safe under concurrent runs). The row is
DELETED again whenever the send does not actually happen (kill-switch,
cooldown, render/send failure) so the slot is never burned by a non-send and
a later retry stays possible.

DDL: migrations/manual/2026-07-12_mail_rail.sql
Spec: docs/active/MAIL_RAIL.md
"""

from __future__ import annotations

import hashlib
import html as _html
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import yaml
from jinja2 import Environment, StrictUndefined

from src.services import smtp_gateway, whatsapp_notify

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent.parent.parent
RAIL_TEMPLATES_DIR = BASE_DIR / "email-templates" / "rail"

FROM_ADDRESS = os.getenv("SECRETARIAT_DEFAULT_FROM_ADDRESS", "").strip()

RELEASABLE_STATUSES = ("pending_approval", "failed")  # failed = retryable

_JINJA = Environment(undefined=StrictUndefined, keep_trailing_newline=False)


def _connect():
    """Open an autocommit psycopg2 connection (each rail statement is atomic
    on its own; the idem INSERT must be visible to concurrent runs at once)."""
    database_url_file = os.getenv("MAIL_RAIL_DATABASE_URL_FILE", "").strip()
    if database_url_file:
        database_url = Path(database_url_file).read_text(encoding="utf-8").strip()
        conn = psycopg2.connect(database_url)
    else:
        database_url = os.getenv("MAIL_RAIL_DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("MAIL_RAIL_DATABASE_URL_FILE or MAIL_RAIL_DATABASE_URL is required")
        conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


# ---------------------------------------------------------------------------
# Template registry — email-templates/rail/<name>.md
# ---------------------------------------------------------------------------


@dataclass
class RailTemplate:
    name: str
    subject_tpl: str
    body_tpl: str
    idem_key_tpl: str
    category: str
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)
    cooldown_days: Optional[int] = None
    description: str = ""
    version: str = ""


def load_rail_template(name: str) -> RailTemplate:
    """Load and parse email-templates/rail/<name>.md.

    Raises ValueError on missing file, malformed frontmatter, or missing
    mandatory frontmatter keys (subject, idem_key, category).
    """
    path = RAIL_TEMPLATES_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(p.stem for p in RAIL_TEMPLATES_DIR.glob("*.md"))
        raise ValueError(f"Rail template not found: {path}. Available: {available}")

    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Rail template {name}: missing YAML frontmatter (must start with ---)")
    try:
        _, fm_block, body = raw.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"Rail template {name}: unterminated YAML frontmatter") from exc

    try:
        meta = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Rail template {name}: invalid YAML frontmatter: {exc}") from exc

    for key in ("subject", "idem_key", "category"):
        if not meta.get(key):
            raise ValueError(f"Rail template {name}: frontmatter key '{key}' is required")

    cooldown = meta.get("cooldown_days")
    return RailTemplate(
        name=name,
        subject_tpl=str(meta["subject"]),
        body_tpl=body.strip(),
        idem_key_tpl=str(meta["idem_key"]),
        category=str(meta["category"]),
        required_params=list(meta.get("required_params") or []),
        optional_params=list(meta.get("optional_params") or []),
        cooldown_days=int(cooldown) if cooldown else None,
        description=str(meta.get("description") or "").strip(),
        version=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def _render(template_str: str, params: dict) -> str:
    """Render a Jinja2 string with StrictUndefined (missing var -> error)."""
    return _JINJA.from_string(template_str).render(**params)


def _text_to_html(text: str) -> str:
    """Escape plain Polish text and wrap paragraphs for the HTML part.

    The result is passed to smtp_gateway as content_html and wrapped in the
    'standard' email template; the untouched text goes as the plain part.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n".join(
        "<p style='margin:0 0 14px 0;'>" + _html.escape(p).replace("\n", "<br>\n") + "</p>"
        for p in paragraphs
    )


# ---------------------------------------------------------------------------
# DB helpers (each takes an open connection; unit tests patch these or feed
# a fake cursor, so keep every statement in one place)
# ---------------------------------------------------------------------------


def _insert_idem_row(
    conn, template: str, company_id: Optional[int], idem_key: str
) -> Optional[int]:
    """Atomic idempotency claim. Returns new row id, or None if the
    (template, company, idem_key) slot is already taken (=> already sent)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mail_rail_sends (template, company_id, idem_key)
            VALUES (%(template)s, %(company_id)s, %(idem_key)s)
            ON CONFLICT (template, COALESCE(company_id, -1), idem_key) DO NOTHING
            RETURNING id
            """,
            {"template": template, "company_id": company_id, "idem_key": idem_key},
        )
        row = cur.fetchone()
    return row[0] if row else None


def _delete_idem_row(conn, row_id: int) -> None:
    """Release an idempotency claim (send did not happen — retry possible)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM mail_rail_sends WHERE id = %(id)s", {"id": row_id})


def _set_idem_send_log_id(conn, row_id: int, send_log_id: Optional[int]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE mail_rail_sends SET send_log_id = %(log_id)s WHERE id = %(id)s",
            {"log_id": send_log_id, "id": row_id},
        )


def _killswitch_active(conn, company_id: Optional[int], category: str) -> bool:
    """True if the company opted out of this category or of all rail mail."""
    if company_id is None:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM mail_rail_optouts
            WHERE company_id = %(company_id)s AND category IN (%(category)s, '*')
            LIMIT 1
            """,
            {"company_id": company_id, "category": category},
        )
        return cur.fetchone() is not None


def _cooldown_hit(
    conn, template: str, company_id: Optional[int], cooldown_days: int, exclude_id: int
) -> bool:
    """True if this template already went to this company within the window
    (any idem_key — extra guard against pestering, e.g. re-asking for a
    statement of a different period days apart)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM mail_rail_sends
            WHERE template = %(template)s
              AND COALESCE(company_id, -1) = COALESCE(%(company_id)s, -1)
              AND id <> %(exclude_id)s
              AND sent_at > now() - (%(days)s * INTERVAL '1 day')
            LIMIT 1
            """,
            {
                "template": template,
                "company_id": company_id,
                "exclude_id": exclude_id,
                "days": cooldown_days,
            },
        )
        return cur.fetchone() is not None


def _lookup_send_log_id(conn, message_id: Optional[str]) -> Optional[int]:
    """Resolve the email_send_log row id written by smtp_gateway for this
    Message-ID (send_email returns the Message-ID but not the log row id)."""
    if not message_id:
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM email_send_log WHERE smtp_message_id = %(mid)s "
            "ORDER BY id DESC LIMIT 1",
            {"mid": message_id},
        )
        row = cur.fetchone()
    return row[0] if row else None


def _insert_draft(conn, fields: dict) -> int:
    """INSERT z dynamiczna lista kolumn: pola opcjonalne (body_html,
    source_registry_id, in_reply_to, references_header) wchodza do SQL tylko
    gdy przekazane i niepuste - dzieki temu create_curated_draft dziala takze
    na schemacie sprzed migracji 2026-07-21_inbound_reply.sql."""
    base = [
        "company_id",
        "from_address",
        "to_address",
        "cc_addresses",
        "subject",
        "body",
        "attachments",
        "log_category",
        "due_at",
        "created_by",
    ]
    optional = ["body_html", "source_registry_id", "in_reply_to", "references_header"]
    cols = list(base) + [k for k in optional if fields.get(k) is not None]
    col_sql = ", ".join(cols)
    val_sql = ", ".join("%(" + k + ")s" for k in cols)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO email_drafts (" + col_sql + ", status) "
            "VALUES (" + val_sql + ", 'pending_approval') RETURNING id",
            {k: fields.get(k) for k in cols},
        )
        return cur.fetchone()[0]


def _set_draft_error(conn, draft_id: int, error: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE email_drafts SET error = %(error)s WHERE id = %(id)s",
            {"error": error, "id": draft_id},
        )


def _claim_draft(
    conn,
    draft_id: int,
    via: str,
    expected_revision: int | None = None,
) -> Optional[dict]:
    """Atomically claim a draft for sending. Only pending_approval (first
    release) or failed (retry after fix) drafts are claimable — this is the
    double-release guard. Returns the claimed row as dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE email_drafts
            SET status = 'approved', decided_at = now(), decision_via = %(via)s
            WHERE id = %(id)s AND status IN ('pending_approval', 'failed')
              AND (
                  %(expected_revision)s IS NULL
                  OR jsonb_array_length(revisions) = %(expected_revision)s
              )
            RETURNING *
            """,
            {"id": draft_id, "via": via, "expected_revision": expected_revision},
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _finalize_draft(
    conn, draft_id: int, status: str, sent_log_id: Optional[int] = None, error: Optional[str] = None
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE email_drafts
            SET status = %(status)s, sent_log_id = %(sent_log_id)s,
                error = %(error)s
            WHERE id = %(id)s
            """,
            {"status": status, "sent_log_id": sent_log_id, "error": error, "id": draft_id},
        )


def _reject_draft_row(
    conn,
    draft_id: int,
    via: str,
    expected_revision: int | None = None,
) -> bool:
    """Reject a pending draft. Returns False if it was not pending_approval."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE email_drafts
            SET status = 'rejected', decided_at = now(), decision_via = %(via)s
            WHERE id = %(id)s AND status = 'pending_approval'
              AND (
                  %(expected_revision)s IS NULL
                  OR jsonb_array_length(revisions) = %(expected_revision)s
              )
            RETURNING id
            """,
            {"id": draft_id, "via": via, "expected_revision": expected_revision},
        )
        return cur.fetchone() is not None


def _fetch_draft(conn, draft_id: int) -> Optional[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM email_drafts WHERE id = %(id)s", {"id": draft_id})
        row = cur.fetchone()
    return dict(row) if row else None


def _fetch_drafts(conn, status: Optional[str], limit: int) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        if status:
            cur.execute(
                "SELECT * FROM email_drafts WHERE status = %(status)s "
                "ORDER BY id DESC LIMIT %(limit)s",
                {"status": status, "limit": limit},
            )
        else:
            cur.execute(
                "SELECT * FROM email_drafts ORDER BY id DESC LIMIT %(limit)s",
                {"limit": limit},
            )
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Shared send plumbing
# ---------------------------------------------------------------------------


def _do_send(
    *,
    to_address: str,
    subject: str,
    body_text: str,
    from_address: str,
    cc: Optional[list[str]],
    attachments: Optional[list[str]],
    company_id: Optional[int],
    log_category: str,
    sent_by: str,
    automation_mode: str | None = None,
    template_key: str | None = None,
    template_version: str | None = None,
    approved_send: bool = False,
    body_html: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[list[str]] = None,
) -> smtp_gateway.SendResult:
    """Single funnel to smtp_gateway.send_email — the ONLY way rail mail
    leaves the building (audited, logged, valid From)."""
    att = [smtp_gateway.Attachment(filepath=p) for p in (attachments or [])]
    return smtp_gateway.send_email(
        to_address=to_address,
        subject=subject,
        content_html=body_html if body_html else _text_to_html(body_text),
        template_name="raw" if body_html else None,
        body_text=body_text,
        from_account=from_address,
        cc=cc,
        attachments=att or None,
        company_id=company_id,
        log_category=log_category,
        sent_by=sent_by,
        approved_send=approved_send,
        automation_mode=automation_mode,
        template_key=template_key,
        template_version=template_version,
        in_reply_to=in_reply_to,
        references=references,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _draft_to_dict(row: dict) -> dict:
    out = {k: _jsonable(v) for k, v in row.items()}
    for key in ("cc_addresses", "attachments"):
        if isinstance(out.get(key), str):
            try:
                out[key] = json.loads(out[key])
            except (ValueError, TypeError):
                pass
    return out


# ---------------------------------------------------------------------------
# Public API — verb 1: autonomous template send
# ---------------------------------------------------------------------------


def send_template(
    template: str,
    company_id: int | None,
    params: dict,
    to_address: str,
    cc: list[str] | None = None,
    attachments: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Send a pre-approved rail template to a client. All guards inside.

    Returns {"status": ..., "send_log_id": ..., "detail": ...} where status is
    one of: sent | skipped_idempotent | skipped_killswitch | skipped_cooldown
    | error | dry_run (dry_run: renders + validates only, touches nothing).

    Flow: load+validate template & params -> render idem_key/subject/body ->
    atomic idem claim (INSERT ... ON CONFLICT DO NOTHING) -> kill-switch ->
    cooldown -> smtp_gateway.send_email -> stamp send_log_id on the idem row.
    Any non-send after the claim releases the idem row (retry possible).
    """
    # 1. Load + validate ----------------------------------------------------
    try:
        tpl = load_rail_template(template)
    except Exception as e:
        return {"status": "error", "send_log_id": None, "detail": f"template load failed: {e}"}

    missing = [p for p in tpl.required_params if params.get(p) is None or params.get(p) == ""]
    if missing:
        return {
            "status": "error",
            "send_log_id": None,
            "detail": f"missing required params: {missing}",
        }

    render_ctx = dict(params)
    render_ctx.setdefault("company_id", company_id)
    # Optional params default to None so {% if %} blocks work without them.
    for p in tpl.optional_params:
        render_ctx.setdefault(p, None)

    # 2. Render everything up front (a render error must precede DB writes) -
    try:
        idem_key = _render(tpl.idem_key_tpl, render_ctx).strip()
        subject = _render(tpl.subject_tpl, render_ctx).strip()
        body_text = _render(tpl.body_tpl, render_ctx).strip()
    except Exception as e:
        return {"status": "error", "send_log_id": None, "detail": f"render failed: {e}"}

    if dry_run:
        return {
            "status": "dry_run",
            "send_log_id": None,
            "detail": {
                "template": template,
                "idem_key": idem_key,
                "to_address": to_address,
                "subject": subject,
                "body": body_text,
                "category": tpl.category,
            },
        }

    # 3. Guards + send ------------------------------------------------------
    try:
        conn = _connect()
    except Exception as e:
        return {"status": "error", "send_log_id": None, "detail": f"db connect failed: {e}"}
    try:
        row_id = _insert_idem_row(conn, template, company_id, idem_key)
        if row_id is None:
            return {
                "status": "skipped_idempotent",
                "send_log_id": None,
                "detail": f"already sent for idem_key={idem_key!r}",
            }

        try:
            if _killswitch_active(conn, company_id, tpl.category):
                _delete_idem_row(conn, row_id)
                return {
                    "status": "skipped_killswitch",
                    "send_log_id": None,
                    "detail": f"company {company_id} opted out of "
                    f"category {tpl.category!r} (mail_rail_optouts)",
                }

            if tpl.cooldown_days and _cooldown_hit(
                conn, template, company_id, tpl.cooldown_days, exclude_id=row_id
            ):
                _delete_idem_row(conn, row_id)
                return {
                    "status": "skipped_cooldown",
                    "send_log_id": None,
                    "detail": f"template {template!r} already sent to company "
                    f"{company_id} within {tpl.cooldown_days} days",
                }

            result = _do_send(
                to_address=to_address,
                subject=subject,
                body_text=body_text,
                from_address=FROM_ADDRESS,
                cc=cc,
                attachments=attachments,
                company_id=company_id,
                log_category=tpl.category,
                sent_by=f"mail_rail:{template}",
                automation_mode="automatic_template",
                template_key=template,
                template_version=tpl.version,
            )
            if not result.success:
                _delete_idem_row(conn, row_id)
                return {
                    "status": "error",
                    "send_log_id": None,
                    "detail": f"send failed: {result.error}",
                }

            send_log_id = _lookup_send_log_id(conn, result.message_id)
            _set_idem_send_log_id(conn, row_id, send_log_id)
            logger.info(
                "mail_rail sent template=%s company=%s idem=%s log_id=%s",
                template,
                company_id,
                idem_key,
                send_log_id,
            )
            return {
                "status": "sent",
                "send_log_id": send_log_id,
                "detail": {
                    "idem_key": idem_key,
                    "subject": subject,
                    "message_id": result.message_id,
                },
            }
        except Exception as e:
            # Claimed but did not send — release the slot so retry works.
            try:
                _delete_idem_row(conn, row_id)
            except Exception:
                logger.exception("mail_rail: failed to release idem row %s", row_id)
            return {
                "status": "error",
                "send_log_id": None,
                "detail": f"unexpected failure after idem claim: {e}",
            }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API — verb 2: curated draft queue (WhatsApp approval)
# ---------------------------------------------------------------------------


def create_curated_draft(
    to_address: str,
    subject: str,
    body: str,
    *,
    company_id: int | None = None,
    cc: list[str] | None = None,
    attachments: list[str] | None = None,
    due_at: str | None = None,
    created_by: str = "orchestrator",
    log_category: str = "curated",
    body_html: str | None = None,
) -> dict:
    """Queue a one-off client mail and optionally notify the operator.

    NOTHING is sent here — release_draft() does the sending after
    an approval (wave-2 poller: TAK <id> / NIE <id> / TREŚĆ <id>).

    WhatsApp failure does NOT fail the call: the draft exists and the nag
    will catch it; the failure is recorded in email_drafts.error.

    Returns {"draft_id": ..., "status": "pending_approval"}.
    """
    conn = _connect()
    try:
        draft_id = _insert_draft(
            conn,
            {
                "company_id": company_id,
                "from_address": FROM_ADDRESS,
                "to_address": to_address,
                "cc_addresses": json.dumps(cc) if cc else None,
                "subject": subject,
                "body": body,
                "body_html": body_html,
                "attachments": json.dumps(attachments) if attachments else None,
                "log_category": log_category,
                "due_at": due_at,
                "created_by": created_by,
            },
        )

        firma = str(company_id) if company_id is not None else "—"
        notify_text = (
            f"[Digital Secretariat mail #{draft_id}] Do zatwierdzenia: {subject} "
            f"→ {to_address} (firma {firma}). "
            f"Odpowiedz: TAK {draft_id} / NIE {draft_id} / TREŚĆ {draft_id}"
        )
        wa = whatsapp_notify.send_whatsapp_dm(notify_text)
        if not wa.get("ok"):
            logger.warning(
                "mail_rail: WhatsApp notify failed for draft %s: %s", draft_id, wa.get("error")
            )
            try:
                _set_draft_error(
                    conn,
                    draft_id,
                    f"whatsapp notify failed: {wa.get('error')}",
                )
            except Exception:
                logger.exception(
                    "mail_rail: could not record notify error on " "draft %s", draft_id
                )

        return {"draft_id": draft_id, "status": "pending_approval"}
    finally:
        conn.close()


def find_recent_duplicate_draft(to_address: str, subject: str, hours: int = 48) -> Optional[dict]:
    """Courtesy duplicate guard for gated one-off mail.

    Returns the newest email_drafts row (id, status, created_at) with the
    same to_address (case-insensitive) + subject, in status
    pending_approval or sent, created within the last `hours`.
    None when no such twin exists.
    """
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, status, created_at
                FROM email_drafts
                WHERE lower(to_address) = lower(%(to)s)
                  AND subject = %(subject)s
                  AND status IN ('pending_approval', 'sent')
                  AND created_at >= now() - make_interval(hours => %(hours)s)
                ORDER BY id DESC
                LIMIT 1
                """,
                {"to": to_address, "subject": subject, "hours": hours},
            )
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _action_conflict(
    draft_id: int,
    existing: dict | None,
    expected_revision: int | None,
    action: str,
) -> dict:
    current = existing["status"] if existing else "missing"
    current_revision = len(existing.get("revisions") or []) if existing else None
    if expected_revision is not None and current_revision != expected_revision:
        return {
            "draft_id": draft_id,
            "status": "error",
            "reason": "stale_revision",
            "detail": (
                f"draft changed (expected revision {expected_revision}, "
                f"current revision {current_revision})"
            ),
        }
    return {
        "draft_id": draft_id,
        "status": "error",
        "detail": f"draft not {action} (status={current})",
    }


def _newer_inbound_from(conn, from_email: str, since) -> Optional[dict]:
    """Return the newest inbound received from the recipient after ``since``."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id::text AS registry_id,
                   COALESCE(subject, '(bez tematu)') AS subject, received_at
            FROM email_processing_registry
            WHERE lower(sender_email) = lower(%(from)s)
              AND received_at > %(since)s
            ORDER BY received_at DESC
            LIMIT 1
            """,
            {"from": from_email, "since": since},
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _draft_last_activity(draft: dict):
    """Timestamp of the latest draft content: last edit or creation."""
    revisions = draft.get("revisions") or []
    if isinstance(revisions, str):
        revisions = json.loads(revisions)
    revision_times = [revision.get("at") for revision in revisions if revision.get("at")]
    return max(revision_times) if revision_times else draft["created_at"]


def release_draft(
    draft_id: int,
    via: str,
    expected_revision: int | None = None,
    force: bool = False,
) -> dict:
    """Approve + send a queued draft. Atomic claim (UPDATE ... WHERE status
    IN pending_approval/failed) guards double-release. On send failure the
    draft lands in 'failed' with the error and stays releasable (retry after
    fix). Returns {"draft_id", "status", ...}.

    The freshness gate refuses a draft when the recipient sent a newer message
    after the latest edit. ``force=True`` is reserved for a separate, explicit
    confirmation after that newer message has been reviewed.
    """
    conn = _connect()
    try:
        if not force:
            pending = _fetch_draft(conn, draft_id)
            if pending is not None and pending.get("status") in ("pending_approval", "failed"):
                newer = _newer_inbound_from(
                    conn,
                    pending["to_address"],
                    _draft_last_activity(pending),
                )
                if newer is not None:
                    return {
                        "draft_id": draft_id,
                        "status": "blocked",
                        "reason": "newer_inbound",
                        "detail": (
                            "A newer message from the recipient arrived after the draft changed; "
                            "review it before sending."
                        ),
                        "newer_inbound": newer,
                    }

        draft = _claim_draft(conn, draft_id, via, expected_revision)
        if draft is None:
            existing = _fetch_draft(conn, draft_id)
            return _action_conflict(draft_id, existing, expected_revision, "releasable")

        if _killswitch_active(
            conn,
            draft.get("company_id"),
            draft.get("log_category") or "curated",
        ):
            detail = "mail rail kill-switch active; nothing was sent"
            _finalize_draft(conn, draft_id, "failed", error=detail)
            return {
                "draft_id": draft_id,
                "status": "failed",
                "reason": "killswitch",
                "detail": detail,
            }

        cc = draft.get("cc_addresses")
        if isinstance(cc, str):
            cc = json.loads(cc)
        attachments = draft.get("attachments")
        if isinstance(attachments, str):
            attachments = json.loads(attachments)

        result = _do_send(
            to_address=draft["to_address"],
            subject=draft["subject"],
            body_text=draft["body"],
            from_address=draft.get("from_address") or FROM_ADDRESS,
            cc=cc,
            attachments=attachments,
            company_id=draft.get("company_id"),
            log_category=draft.get("log_category") or "curated",
            sent_by=f"mail_rail:curated:{via}",
            automation_mode="formatted_approved",
            approved_send=True,  # draft zatwierdzony — jedyna furtka w OUTBOUND_FREEZE
            body_html=draft.get("body_html"),
            in_reply_to=draft.get("in_reply_to"),
            references=(draft.get("references_header") or "").split() or None,
        )

        if result.success:
            send_log_id = _lookup_send_log_id(conn, result.message_id)
            _finalize_draft(conn, draft_id, "sent", sent_log_id=send_log_id)
            # Kontrakt ly05: rejestr oznaczamy TYLKO w sciezce potwierdzonego
            # sukcesu (nigdy przy samym drafcie ani po nieudanym SMTP).
            if draft.get("source_registry_id"):
                _mark_registry_replied(conn, draft["source_registry_id"])
            logger.info("mail_rail: draft %s sent via %s (log_id=%s)", draft_id, via, send_log_id)
            return {
                "draft_id": draft_id,
                "status": "sent",
                "sent_log_id": send_log_id,
                "detail": {"message_id": result.message_id},
            }

        _finalize_draft(conn, draft_id, "failed", error=result.error)
        return {"draft_id": draft_id, "status": "failed", "detail": f"send failed: {result.error}"}
    finally:
        conn.close()


def edit_draft(
    draft_id: int,
    *,
    body: str | None = None,
    subject: str | None = None,
    via: str = "orchestrator",
    expected_revision: int | None = None,
) -> dict:
    """Edit a queued draft's body and/or subject BEFORE approval.

    Only pending_approval drafts are editable — an approved/sent/rejected
    draft is history and stays immutable. The pre-edit version is appended
    to email_drafts.revisions (audit trail), so the approver can always see
    what changed. Returns {"draft_id", "status", "revision_count", ...}.
    """
    if body is None and subject is None:
        return {
            "draft_id": draft_id,
            "status": "error",
            "detail": "nothing to edit (body and subject both empty)",
        }
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE email_drafts
                SET revisions = revisions || jsonb_build_array(jsonb_build_object(
                        'at', now(), 'via', %(via)s,
                        'old_subject', subject, 'old_body', body)),
                    subject = COALESCE(%(subject)s, subject),
                    body = COALESCE(%(body)s, body)
                WHERE id = %(id)s AND status = 'pending_approval'
                  AND (
                      %(expected_revision)s IS NULL
                      OR jsonb_array_length(revisions) = %(expected_revision)s
                  )
                RETURNING id, subject, jsonb_array_length(revisions) AS revision_count
                """,
                {
                    "id": draft_id,
                    "via": via,
                    "subject": subject,
                    "body": body,
                    "expected_revision": expected_revision,
                },
            )
            row = cur.fetchone()
        if row is None:
            existing = _fetch_draft(conn, draft_id)
            return _action_conflict(draft_id, existing, expected_revision, "editable")
        logger.info(
            "mail_rail: draft %s edited via %s (revision %s)", draft_id, via, row["revision_count"]
        )
        return {
            "draft_id": draft_id,
            "status": "pending_approval",
            "revision_count": row["revision_count"],
            "subject": row["subject"],
        }
    finally:
        conn.close()


def reject_draft(
    draft_id: int,
    via: str,
    expected_revision: int | None = None,
) -> dict:
    """Reject a pending draft (NIE <id>). Only pending_approval drafts can be
    rejected. Returns {"draft_id", "status", ...}."""
    conn = _connect()
    try:
        if _reject_draft_row(conn, draft_id, via, expected_revision):
            return {"draft_id": draft_id, "status": "rejected"}
        existing = _fetch_draft(conn, draft_id)
        return _action_conflict(draft_id, existing, expected_revision, "rejectable")
    finally:
        conn.close()


def get_draft(draft_id: int) -> Optional[dict]:
    """Fetch one draft (timestamps as ISO strings), or None."""
    conn = _connect()
    try:
        row = _fetch_draft(conn, draft_id)
        return _draft_to_dict(row) if row else None
    finally:
        conn.close()


def list_drafts(status: str | None = None, limit: int = 50) -> list[dict]:
    """List drafts, newest first, optionally filtered by status."""
    conn = _connect()
    try:
        return [_draft_to_dict(r) for r in _fetch_drafts(conn, status, limit)]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API — verb 3: reply draft to a registered inbound message
# The source registry remains authoritative for sender, mailbox, and threading.
# ---------------------------------------------------------------------------


class MailRailError(Exception):
    """Maszynowo rozróżnialny błąd domenowy szyny (UI czyta code, nie tekst)."""

    def __init__(
        self, code: str, detail: str = "", draft_id: int | None = None, status: str | None = None
    ):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.draft_id = draft_id
        self.status = status


_ACTIVE_REPLY_STATUSES = ("pending_approval", "approved", "sent", "failed")


def _subject_with_re(subject: str) -> str:
    """RFC-bezpieczny pojedynczy prefiks Re: (bez dublowania, bez CR/LF)."""
    s = " ".join((subject or "").replace("\r", " ").replace("\n", " ").split())
    if not s:
        return ""
    if s.lower().startswith("re:"):
        return s[:998]
    return ("Re: " + s)[:998]


def _valid_single_address(addr: str) -> bool:
    if not addr or any(ch in addr for ch in "\r\n,;<> "):
        return False
    local, sep, domain = addr.partition("@")
    return bool(sep and local and "." in domain)


def _angle(mid: str) -> str:
    mid = (mid or "").strip()
    if mid and not mid.startswith("<"):
        return f"<{mid}>"
    return mid


_MSGID_RE = re.compile(r"^<[!-;=?-~]+@[!-;=?-~]+>$")


def _valid_msgid(token: str) -> bool:
    """B4: Message-ID z inbound to dane NIEUFNE — samo dopięcie <> nie jest
    walidacją. Odrzucamy CR/LF, spacje, wielokrotne @ i tokeny spoza RFC."""
    if not token or any(ch in token for ch in "\r\n\t "):
        return False
    return bool(_MSGID_RE.match(token)) and token.count("@") == 1


def _mark_registry_replied(conn, registry_id) -> None:
    """Sukces wysyłki odpowiedzi → rejestr wpływu dostaje response_sent=true,
    response_type='human'. Wołane WYŁĄCZNIE ze ścieżki sukcesu release_draft."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE email_processing_registry
            SET response_sent = true,
                response_type = 'human',
                processed_at = COALESCE(processed_at, now())
            WHERE id = %(rid)s
            """,
            {"rid": str(registry_id)},
        )


def create_reply_draft(
    registry_id: str,
    body: str,
    *,
    subject: str | None = None,
    created_by: str,
) -> dict:
    """Utwórz draft odpowiedzi na zarejestrowany wpływ (email_processing_registry).

    Serwer wyprowadza adresata (sender_email), nadawcę (recipient_address —
    skrzynka, na której mail przyszedł), firmę i nagłówki wątku. Przeglądarka
    dostarcza wyłącznie treść i opcjonalny temat. NIGDY nie wysyła — wysyłka
    to release_draft po ludzkim zatwierdzeniu.

    Raises MailRailError(code=...): source_not_found, invalid_body,
    invalid_subject, invalid_sender, source_mailbox_unknown,
    source_mailbox_unavailable, reply_already_exists.
    """
    import uuid as _uuid

    try:
        rid = str(_uuid.UUID(str(registry_id)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise MailRailError("source_not_found", "registry_id nie jest poprawnym UUID") from exc

    body_clean = (body or "").strip()
    if not (1 <= len(body_clean) <= 10_000):
        raise MailRailError("invalid_body", "treść po strip() musi mieć 1–10000 znaków")

    conn = _connect()
    conn.autocommit = False  # jedna transakcja: lock rejestru + insert draftu
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, message_id, sender_email, subject, company_id,
                       in_reply_to, references_header, recipient_address
                FROM email_processing_registry
                WHERE id = %(rid)s
                FOR UPDATE
                """,
                {"rid": rid},
            )
            src = cur.fetchone()
        if not src:
            raise MailRailError("source_not_found", f"brak wpisu rejestru {rid}")

        sender = (src["sender_email"] or "").strip().lower()
        if not _valid_single_address(sender):
            raise MailRailError(
                "invalid_sender", "nadawca źródła nie jest pojedynczym poprawnym adresem"
            )
        local = sender.split("@", 1)[0]
        if "no-reply" in local or "noreplyy" in local or "noreply" in local:
            raise MailRailError("invalid_sender", "adres nadawcy to no-reply")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT lower(email_address) FROM system_email_accounts WHERE is_active = true"
            )
            own_active = {r[0] for r in cur.fetchall()}
        if sender in own_active:
            raise MailRailError(
                "invalid_sender", "nadawca to własna aktywna skrzynka — to nie jest mail klienta"
            )

        mailbox = (src["recipient_address"] or "").strip().lower()
        if not mailbox:
            raise MailRailError(
                "source_mailbox_unknown",
                "rejestr nie ma utrwalonej skrzynki odbiorczej (recipient_address); "
                "backfill wyłącznie z dowodu cache/IMAP — nie zgadujemy",
            )
        if mailbox not in own_active:
            raise MailRailError(
                "source_mailbox_unavailable",
                f"skrzynka {mailbox} nie jest aktywnym kontem wysyłkowym",
            )

        subj = _subject_with_re(subject if subject is not None else (src["subject"] or ""))
        if not subj:
            raise MailRailError("invalid_subject", "temat po normalizacji jest pusty")

        # Guard duplikatu (przyjazna ścieżka; wyścig łapie unikalny indeks częściowy)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status FROM email_drafts
                WHERE source_registry_id = %(rid)s
                  AND status IN %(st)s
                LIMIT 1
                """,
                {"rid": rid, "st": _ACTIVE_REPLY_STATUSES},
            )
            dup = cur.fetchone()
        if dup:
            raise MailRailError(
                "reply_already_exists",
                "istnieje aktywna odpowiedź na ten wpływ",
                draft_id=dup[0],
                status=dup[1],
            )

        mid = _angle(src["message_id"])
        if not _valid_msgid(mid):
            raise MailRailError(
                "invalid_source_headers",
                "Message-ID źródła nie jest poprawnym tokenem RFC — możliwa "
                "próba header injection; odpowiedź wymaga ścieżki ręcznej",
            )
        refs_parts: list[str] = []
        for token in (src["references_header"] or "").split() + [mid]:
            t = _angle(token)
            if t and _valid_msgid(t) and t not in refs_parts:
                refs_parts.append(t)

        try:
            draft_id = _insert_draft(
                conn,
                {
                    "company_id": src["company_id"],  # NULL = nowa relacja, poprawne
                    "from_address": mailbox,
                    "to_address": sender,
                    "cc_addresses": None,
                    "subject": subj,
                    "body": body_clean,
                    "attachments": None,
                    "log_category": "inbound_reply",
                    "due_at": None,
                    "created_by": created_by,
                    "source_registry_id": rid,
                    "in_reply_to": mid,
                    "references_header": " ".join(refs_parts),
                },
            )
        except psycopg2.errors.UniqueViolation as exc:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, status FROM email_drafts WHERE source_registry_id=%(rid)s "
                    "AND status IN %(st)s LIMIT 1",
                    {"rid": rid, "st": _ACTIVE_REPLY_STATUSES},
                )
                dup = cur.fetchone()
            raise MailRailError(
                "reply_already_exists",
                "równoległa odpowiedź wygrała wyścig",
                draft_id=dup[0] if dup else None,
                status=dup[1] if dup else None,
            ) from exc
        conn.commit()
        return {
            "draft_id": draft_id,
            "status": "pending_approval",
            "source_registry_id": rid,
            "revision_count": 0,
        }
    except MailRailError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
