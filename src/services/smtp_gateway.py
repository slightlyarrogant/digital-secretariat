"""
SMTP Gateway — single canonical SMTP sender for Digital Secretariat adapters.

Reads credentials from system_email_accounts table.
Logs every send to email_send_log table.
Synchronous implementation used behind the audited mail rail.

Template system:
  - email-templates/<name>.html — HTML templates with {{CONTENT}} placeholder
  - email-attachments/          — Default root for relative attachment paths
"""

import json
import logging
import mimetypes
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from src.database.sync_connection import SessionLocal
from src.services.email_headers import MissingFromAddressError, apply_standard_headers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "email-templates"
ATTACHMENTS_DIR = BASE_DIR / "email-attachments"

# ---------------------------------------------------------------------------
# OUTBOUND FREEZE — fail closed until a human-approved draft reaches the gateway.
# ---------------------------------------------------------------------------
OUTBOUND_FREEZE = os.getenv("SECRETARIAT_OUTBOUND_FREEZE", "true").casefold() != "false"
_FREEZE_ALLOWED_DOMAINS = tuple(
    value.strip().casefold()
    for value in os.getenv("SECRETARIAT_FREEZE_ALLOWED_DOMAINS", "").split(",")
    if value.strip()
)
_FREEZE_ALLOWED_ADDRESSES = {
    value.strip().casefold()
    for value in os.getenv("SECRETARIAT_FREEZE_ALLOWED_ADDRESSES", "").split(",")
    if value.strip()
}


def _freeze_blocks(addr):
    if not addr:
        return False
    a = addr.strip().lower()
    if a in _FREEZE_ALLOWED_ADDRESSES:
        return False
    return not any(a.endswith(d) for d in _FREEZE_ALLOWED_DOMAINS)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Attachment:
    filepath: str
    display_name: Optional[str] = None


@dataclass
class SendResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------


def render_template(template_name: str, content_html: str) -> str:
    """
    Load TEMPLATES_DIR/<template_name>.html and substitute {{CONTENT}}.

    Args:
        template_name: Filename stem, e.g. "standard"
        content_html:  The inner HTML to inject at {{CONTENT}}

    Returns:
        Fully rendered HTML string.

    Raises:
        ValueError: If the template file does not exist.
    """
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        raise ValueError(
            f"Email template not found: {template_path}. "
            f"Available templates: {[p.stem for p in TEMPLATES_DIR.glob('*.html')]}"
        )
    template_src = template_path.read_text(encoding="utf-8")
    return template_src.replace("{{CONTENT}}", content_html)


# ---------------------------------------------------------------------------
# Attachment path resolver
# ---------------------------------------------------------------------------


def _resolve_attachment_path(filepath: str) -> str:
    """
    If filepath is absolute, return as-is.
    Otherwise resolve relative to ATTACHMENTS_DIR.
    """
    if os.path.isabs(filepath):
        return filepath
    return str(ATTACHMENTS_DIR / filepath)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _html_to_text(html: str) -> str:
    """Strip HTML tags to produce plain-text fallback."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _get_smtp_credentials(from_address: str) -> dict:
    """Look up SMTP credentials from system_email_accounts."""
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT smtp_host, smtp_port, smtp_username, smtp_password "
                "FROM system_email_accounts "
                "WHERE email_address = :addr AND is_active = true"
            ),
            {"addr": from_address},
        ).fetchone()
    if not row:
        raise ValueError(f"No active SMTP account found for {from_address}")
    return {
        "host": row.smtp_host,
        "port": row.smtp_port,
        "username": row.smtp_username,
        "password": row.smtp_password,
    }


def _log_send(
    from_address: str,
    to_address: str,
    subject: str,
    body_html: str,
    result: SendResult,
    cc: Optional[list[str]] = None,
    attachments: Optional[list[Attachment]] = None,
    company_id: Optional[int] = None,
    log_category: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    sent_by: str = "orchestrator",
    automation_mode: Optional[str] = None,
    template_key: Optional[str] = None,
    template_version: Optional[str] = None,
) -> None:
    """Log every send attempt to email_send_log."""
    try:
        preview = _html_to_text(body_html)[:500] if body_html else None
        att_meta = None
        if attachments:
            att_meta = json.dumps(
                [{"filepath": a.filepath, "display_name": a.display_name} for a in attachments]
            )

        with SessionLocal() as db:
            db.execute(
                text(
                    "INSERT INTO email_send_log "
                    "(from_address, to_address, cc_addresses, subject, body_preview, "
                    " attachments_metadata, company_id, log_category, smtp_message_id, "
                    " success, error_message, in_reply_to, sent_by, automation_mode, "
                    " template_key, template_version) "
                    "VALUES (:from_addr, :to_addr, :cc, :subject, :preview, "
                    " :att_meta, :company_id, :category, :msg_id, "
                    " :success, :error, :reply_to, :sent_by, :automation_mode, "
                    " :template_key, :template_version)"
                ),
                {
                    "from_addr": from_address,
                    "to_addr": to_address,
                    "cc": json.dumps(cc) if cc else None,
                    "subject": subject,
                    "preview": preview,
                    "att_meta": att_meta,
                    "company_id": company_id,
                    "category": log_category,
                    "msg_id": result.message_id,
                    "success": result.success,
                    "error": result.error,
                    "reply_to": in_reply_to,
                    "sent_by": sent_by,
                    "automation_mode": automation_mode,
                    "template_key": template_key,
                    "template_version": template_version,
                },
            )
            db.commit()
    except Exception as e:
        logger.error(f"Failed to log email send: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def send_email(
    to_address: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    from_account: str = "",
    cc: Optional[list[str]] = None,
    bcc: Optional[list[str]] = None,
    reply_to: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[list[str]] = None,
    attachments: Optional[list[Attachment]] = None,
    company_id: Optional[int] = None,
    log_category: Optional[str] = None,
    sent_by: str = "orchestrator",
    automation_mode: Optional[str] = None,
    template_key: Optional[str] = None,
    template_version: Optional[str] = None,
    # --- Template system ---
    template_name: Optional[str] = None,
    content_html: Optional[str] = None,
    # --- Outbound freeze (2026-07-20) ---
    approved_send: bool = False,
) -> SendResult:
    """
    Send an email via SMTP. Credentials fetched from DB. Logged to email_send_log.

    Template mode (preferred):
        Pass content_html (inner body HTML) and optionally template_name (default "standard").
        The system wraps content_html in the named template, which references the logo via URL.
        Pass template_name="raw" to skip template wrapping (use content_html as-is).

    Legacy mode:
        Pass body_html directly (full HTML). No template wrapping.

    Args:
        to_address:    Recipient email address
        subject:       Email subject line
        body_html:     Full HTML body (legacy; used when content_html is not provided)
        body_text:     Plain-text fallback (auto-generated from HTML if omitted)
        from_account:  Sender address (must exist in system_email_accounts)
        cc, bcc:       Optional recipient lists
        reply_to:      Optional Reply-To header
        in_reply_to:   Message-ID for threading
        references:    Message-ID list for threading
        attachments:   List of Attachment(filepath, display_name)
        company_id:    For audit logging
        log_category:  onboarding|monthly_report|document_delivery|reminder|ad_hoc
        sent_by:       Who initiated the send
        automation_mode: Proven origin of this send, or None when unknown.
        template_key: Stable identifier of the response template.
        template_version: Immutable template version or content hash.
        template_name: Template stem under email-templates/ (default "standard").
                       Pass "raw" to use content_html without wrapping.
        content_html:  Inner HTML content — template wraps this (overrides body_html).
    """
    # ------------------------------------------------------------------
    # OUTBOUND FREEZE gate — external recipients require an approved draft
    # ------------------------------------------------------------------
    if OUTBOUND_FREEZE and not approved_send:
        externals = [a for a in [to_address, *(cc or []), *(bcc or [])] if _freeze_blocks(a)]
        if externals:
            result = SendResult(
                success=False,
                error=(
                    "BLOCKED-FREEZE: wysyłka do adresów zewnętrznych bez zatwierdzenia "
                    f"({', '.join(externals)})."
                ),
            )
            logger.warning(
                "OUTBOUND FREEZE: zablokowano wysyłkę do %s (sent_by: %s)", externals, sent_by
            )
            _log_send(
                from_account,
                to_address,
                subject,
                content_html or body_html or "",
                result,
                cc=cc,
                attachments=attachments,
                company_id=company_id,
                log_category=log_category,
                in_reply_to=in_reply_to,
                sent_by=sent_by,
            )
            return result

    # ------------------------------------------------------------------
    # Determine final HTML body
    # ------------------------------------------------------------------
    if content_html:
        if template_name == "raw":
            final_html = content_html
        else:
            tpl = template_name or "standard"
            try:
                final_html = render_template(tpl, content_html)
            except ValueError as e:
                result = SendResult(success=False, error=str(e))
                _log_send(
                    from_account,
                    to_address,
                    subject,
                    content_html,
                    result,
                    cc=cc,
                    attachments=attachments,
                    company_id=company_id,
                    log_category=log_category,
                    in_reply_to=in_reply_to,
                    sent_by=sent_by,
                    automation_mode=automation_mode,
                    template_key=template_key,
                    template_version=template_version,
                )
                return result
    elif body_html:
        final_html = body_html
    else:
        result = SendResult(
            success=False, error="Either body_html or content_html must be provided"
        )
        _log_send(
            from_account,
            to_address,
            subject,
            "",
            result,
            cc=cc,
            attachments=attachments,
            company_id=company_id,
            log_category=log_category,
            in_reply_to=in_reply_to,
            sent_by=sent_by,
            automation_mode=automation_mode,
            template_key=template_key,
            template_version=template_version,
        )
        return result

    # ------------------------------------------------------------------
    # Get SMTP credentials
    # ------------------------------------------------------------------
    try:
        creds = _get_smtp_credentials(from_account)
    except ValueError as e:
        result = SendResult(success=False, error=str(e))
        _log_send(
            from_account,
            to_address,
            subject,
            final_html,
            result,
            cc=cc,
            attachments=attachments,
            company_id=company_id,
            log_category=log_category,
            in_reply_to=in_reply_to,
            sent_by=sent_by,
            automation_mode=automation_mode,
            template_key=template_key,
            template_version=template_version,
        )
        return result

    # ------------------------------------------------------------------
    # Plain-text fallback
    # ------------------------------------------------------------------
    if not body_text:
        body_text = _html_to_text(final_html)

    # ------------------------------------------------------------------
    # Resolve attachment paths
    # ------------------------------------------------------------------
    resolved_attachments: list[Attachment] = []
    if attachments:
        for att in attachments:
            resolved_path = _resolve_attachment_path(att.filepath)
            resolved_attachments.append(
                Attachment(
                    filepath=resolved_path,
                    display_name=att.display_name,
                )
            )

    has_attachments = bool(resolved_attachments)

    # ------------------------------------------------------------------
    # Build MIME tree
    #
    # has_attachments → multipart/mixed
    #                     multipart/alternative (plain + html)
    #                     application/... (attachments)
    # no attachments  → multipart/alternative (plain + html)
    # ------------------------------------------------------------------

    if has_attachments:
        msg = MIMEMultipart("mixed")
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(body_text, "plain", "utf-8"))
        body_part.attach(MIMEText(final_html, "html", "utf-8"))
        msg.attach(body_part)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(final_html, "html", "utf-8"))

    # Attach files
    for att in resolved_attachments:
        if not os.path.exists(att.filepath):
            logger.warning(f"Attachment not found: {att.filepath}, skipping")
            continue
        with open(att.filepath, "rb") as f:
            file_data = f.read()
        content_type = mimetypes.guess_type(att.filepath)[0] or "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        part = MIMEApplication(file_data, _subtype=subtype)
        filename = att.display_name or os.path.basename(att.filepath)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)
        logger.info(f"Attached: {filename} ({os.path.getsize(att.filepath)} bytes)")

    # ------------------------------------------------------------------
    # Headers — From / Message-ID / Date guaranteed via shared builder
    # (RFC 5322 / Gmail 550-5.7.1 guard). from_account comes from the caller
    # and must exist in system_email_accounts.
    # ------------------------------------------------------------------
    msg["To"] = to_address
    try:
        apply_standard_headers(
            msg,
            from_address=from_account,
            from_name=os.getenv("SECRETARIAT_FROM_NAME", "Digital Secretariat").strip(),
            subject=subject,
        )
    except MissingFromAddressError as e:
        result = SendResult(success=False, error=str(e))
        _log_send(
            from_account,
            to_address,
            subject,
            final_html,
            result,
            cc=cc,
            attachments=resolved_attachments or attachments,
            company_id=company_id,
            log_category=log_category,
            in_reply_to=in_reply_to,
            sent_by=sent_by,
            automation_mode=automation_mode,
            template_key=template_key,
            template_version=template_version,
        )
        return result
    message_id = msg["Message-ID"]

    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = " ".join(references)

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------
    recipients = [to_address]
    if cc:
        recipients.extend(cc)
    if bcc:
        recipients.extend(bcc)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(creds["host"], creds["port"], context=context, timeout=30) as server:
            server.login(creds["username"], creds["password"])
            server.send_message(msg, from_addr=from_account, to_addrs=recipients)

        result = SendResult(success=True, message_id=message_id)
        logger.info(f"Email sent to {to_address} (Message-ID: {message_id})")

    except smtplib.SMTPAuthenticationError as e:
        result = SendResult(success=False, error=f"SMTP auth failed: {e}")
        logger.error(result.error)
    except smtplib.SMTPException as e:
        result = SendResult(success=False, error=f"SMTP error: {e}")
        logger.error(result.error)
    except Exception as e:
        result = SendResult(success=False, error=f"Unexpected error: {e}")
        logger.error(result.error)

    # ------------------------------------------------------------------
    # Log
    # ------------------------------------------------------------------
    _log_send(
        from_account,
        to_address,
        subject,
        final_html,
        result,
        cc=cc,
        attachments=resolved_attachments or attachments,
        company_id=company_id,
        log_category=log_category,
        in_reply_to=in_reply_to,
        sent_by=sent_by,
        automation_mode=automation_mode,
        template_key=template_key,
        template_version=template_version,
    )

    return result
