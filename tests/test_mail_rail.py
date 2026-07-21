"""
Unit tests for src/services/mail_rail.py (bead Digital Secretariat-q1av).

Covers:
- template validation: unknown template / missing required param -> error,
  no DB touched, no send
- dry_run renders both v1 templates without any DB or SMTP activity
- idempotency: occupied (template, company, idem_key) slot -> skipped_idempotent;
  a failed send RELEASES the idem row so retry stays possible
- kill-switch (mail_rail_optouts) and cooldown skips release the idem row too
- draft lifecycle against a fake email_drafts cursor emulating the real SQL:
  create -> WhatsApp notify format, release once, double-release guarded,
  failed release retryable, reject
- WhatsApp notify failure does NOT fail draft creation (recorded in error)

All tests use mocks/fakes — no live sends, no real database.
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.services import mail_rail
from src.services.smtp_gateway import SendResult

PARAMS_BANK = {"company_name": "Testowa Sp. z o.o.", "period": "czerwiec 2026"}
PARAMS_TRIAL = {
    "company_name": "Testowa Sp. z o.o.",
    "period": "czerwca 2026",
    "amount_summary": "Obsługa księgowa: 499,00 zł netto (613,77 zł brutto)",
}
TO = "klient@example.com"


@pytest.fixture(autouse=True)
def configured_default_sender(monkeypatch):
    monkeypatch.setattr(mail_rail, "FROM_ADDRESS", "office@example.com")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_send_guards(*, idem_row=1, killswitch=False, cooldown=False, send_log_id=77):
    """Patch every DB helper send_template touches (fake-conn pattern)."""
    return (
        mock.patch.object(mail_rail, "_connect", return_value=mock.MagicMock()),
        mock.patch.object(mail_rail, "_insert_idem_row", return_value=idem_row),
        mock.patch.object(mail_rail, "_delete_idem_row"),
        mock.patch.object(mail_rail, "_killswitch_active", return_value=killswitch),
        mock.patch.object(mail_rail, "_cooldown_hit", return_value=cooldown),
        mock.patch.object(mail_rail, "_set_idem_send_log_id"),
        mock.patch.object(mail_rail, "_lookup_send_log_id", return_value=send_log_id),
    )


# ---------------------------------------------------------------------------
# 1. Template validation
# ---------------------------------------------------------------------------


def test_unknown_template_is_error_without_db_or_send():
    with (
        mock.patch.object(mail_rail, "_connect") as connect,
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.send_template("no_such_template", 30, PARAMS_BANK, TO)

    assert result["status"] == "error"
    assert "not found" in result["detail"]
    connect.assert_not_called()
    send.assert_not_called()


def test_missing_required_param_is_error_without_db_or_send():
    with (
        mock.patch.object(mail_rail, "_connect") as connect,
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, {"company_name": "X"}, TO)

    assert result["status"] == "error"
    assert "period" in result["detail"]
    connect.assert_not_called()
    send.assert_not_called()


def test_both_v1_templates_load_with_mandatory_frontmatter():
    for name in ("missing_bank_statement", "trial_end_invoice"):
        tpl = mail_rail.load_rail_template(name)
        assert tpl.subject_tpl and tpl.idem_key_tpl and tpl.category
        assert tpl.required_params  # v1 templates all take params


# ---------------------------------------------------------------------------
# 2. dry_run — renders everything, touches nothing
# ---------------------------------------------------------------------------


def test_dry_run_renders_both_templates_without_db_or_send():
    with (
        mock.patch.object(mail_rail, "_connect") as connect,
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        r1 = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO, dry_run=True)
        r2 = mail_rail.send_template("trial_end_invoice", 30, PARAMS_TRIAL, TO, dry_run=True)

    connect.assert_not_called()
    send.assert_not_called()

    assert r1["status"] == "dry_run"
    assert r1["detail"]["idem_key"] == "30:czerwiec 2026"
    assert "czerwiec 2026" in r1["detail"]["subject"]
    assert "wyciągu bankowego" in r1["detail"]["body"]

    assert r2["status"] == "dry_run"
    assert PARAMS_TRIAL["amount_summary"] in r2["detail"]["body"]
    assert "okres próbny" in r2["detail"]["body"]


def test_dry_run_optional_bank_hint_renders_account_list():
    params = dict(PARAMS_BANK, bank_hint=["mBank ...1234", "Santander ...9876"])
    result = mail_rail.send_template("missing_bank_statement", 30, params, TO, dry_run=True)

    assert result["status"] == "dry_run"
    assert "mBank ...1234" in result["detail"]["body"]
    assert "Santander ...9876" in result["detail"]["body"]


# ---------------------------------------------------------------------------
# 3. Idempotency / kill-switch / cooldown
# ---------------------------------------------------------------------------


def test_second_send_skipped_idempotent():
    patches = _patch_send_guards(idem_row=None)  # slot already occupied
    with (
        patches[0],
        patches[1],
        patches[2] as delete_row,
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO)

    assert result["status"] == "skipped_idempotent"
    send.assert_not_called()
    delete_row.assert_not_called()  # nothing was claimed


def test_killswitch_skips_and_releases_idem_row():
    patches = _patch_send_guards(idem_row=11, killswitch=True)
    with (
        patches[0],
        patches[1],
        patches[2] as delete_row,
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO)

    assert result["status"] == "skipped_killswitch"
    send.assert_not_called()
    delete_row.assert_called_once()
    assert delete_row.call_args[0][1] == 11


def test_cooldown_skips_and_releases_idem_row():
    patches = _patch_send_guards(idem_row=12, cooldown=True)
    with (
        patches[0],
        patches[1],
        patches[2] as delete_row,
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO)

    assert result["status"] == "skipped_cooldown"
    send.assert_not_called()
    delete_row.assert_called_once()
    assert delete_row.call_args[0][1] == 12


def test_send_failure_releases_idem_row_for_retry():
    patches = _patch_send_guards(idem_row=13)
    with (
        patches[0],
        patches[1],
        patches[2] as delete_row,
        patches[3],
        patches[4],
        patches[5] as stamp,
        patches[6],
        mock.patch.object(
            mail_rail.smtp_gateway,
            "send_email",
            return_value=SendResult(success=False, error="SMTP auth failed"),
        ) as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO)

    assert result["status"] == "error"
    assert "SMTP auth failed" in result["detail"]
    send.assert_called_once()
    delete_row.assert_called_once()
    assert delete_row.call_args[0][1] == 13
    stamp.assert_not_called()


def test_successful_send_goes_through_gateway_and_stamps_log_id():
    patches = _patch_send_guards(idem_row=14, send_log_id=77)
    with (
        patches[0],
        patches[1],
        patches[2] as delete_row,
        patches[3],
        patches[4],
        patches[5] as stamp,
        patches[6],
        mock.patch.object(
            mail_rail.smtp_gateway,
            "send_email",
            return_value=SendResult(success=True, message_id="<msg-1@x>"),
        ) as send,
    ):
        result = mail_rail.send_template("missing_bank_statement", 30, PARAMS_BANK, TO)

    assert result["status"] == "sent"
    assert result["send_log_id"] == 77
    delete_row.assert_not_called()
    stamp.assert_called_once()
    assert stamp.call_args[0][1:] == (14, 77)

    kwargs = send.call_args.kwargs
    assert kwargs["to_address"] == TO
    assert kwargs["from_account"] == "office@example.com"
    assert kwargs["log_category"] == "reminder"  # from frontmatter
    assert kwargs["sent_by"] == "mail_rail:missing_bank_statement"
    assert kwargs["automation_mode"] == "automatic_template"
    assert kwargs["template_key"] == "missing_bank_statement"
    assert len(kwargs["template_version"]) == 64
    assert kwargs["company_id"] == 30
    assert "wyciągu bankowego" in kwargs["body_text"]


# ---------------------------------------------------------------------------
# 4. Draft lifecycle — REAL SQL helpers against a fake email_drafts cursor
#    (the fake emulates exactly the statements mail_rail issues, including
#    the status-guarded claim/reject UPDATEs that prevent double-release)
# ---------------------------------------------------------------------------


class _FakeDraftDb:
    def __init__(self):
        self.rows = {}
        self._next_id = 1


class _FakeDraftCursor:
    """Emulates the email_drafts statements issued by mail_rail helpers."""

    def __init__(self, db: _FakeDraftDb, dict_rows: bool):
        self.db = db
        self.dict_rows = dict_rows
        self._results = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._results = []
        if "INSERT INTO email_drafts" in sql:
            row_id = self.db._next_id
            self.db._next_id += 1
            self.db.rows[row_id] = {
                "id": row_id,
                "status": "pending_approval",
                "decided_at": None,
                "decision_via": None,
                "sent_log_id": None,
                "error": None,
                "created_at": None,
                "revisions": [],
                **params,
            }
            self._results = [self._shape({"id": row_id})]
        elif "SET revisions =" in sql:
            row = self.db.rows.get(params["id"])
            revision_matches = (
                (
                    params.get("expected_revision") is None
                    or len(row["revisions"]) == params["expected_revision"]
                )
                if row
                else False
            )
            if row and row["status"] == "pending_approval" and revision_matches:
                row["revisions"].append(
                    {
                        "via": params["via"],
                        "old_subject": row["subject"],
                        "old_body": row["body"],
                    }
                )
                row["subject"] = params["subject"] or row["subject"]
                row["body"] = params["body"] or row["body"]
                self._results = [
                    self._shape(
                        {
                            "id": row["id"],
                            "subject": row["subject"],
                            "revision_count": len(row["revisions"]),
                        }
                    )
                ]
        elif "SET status = 'approved'" in sql:
            row = self.db.rows.get(params["id"])
            revision_matches = (
                (
                    params.get("expected_revision") is None
                    or len(row["revisions"]) == params["expected_revision"]
                )
                if row
                else False
            )
            if row and row["status"] in ("pending_approval", "failed") and revision_matches:
                row["status"] = "approved"
                row["decision_via"] = params["via"]
                self._results = [self._shape(dict(row))]
        elif "SET status = 'rejected'" in sql:
            row = self.db.rows.get(params["id"])
            revision_matches = (
                (
                    params.get("expected_revision") is None
                    or len(row["revisions"]) == params["expected_revision"]
                )
                if row
                else False
            )
            if row and row["status"] == "pending_approval" and revision_matches:
                row["status"] = "rejected"
                row["decision_via"] = params["via"]
                self._results = [self._shape({"id": row["id"]})]
        elif "SET error =" in sql:
            self.db.rows[params["id"]]["error"] = params["error"]
        elif "SET status = %(status)s" in sql:
            row = self.db.rows[params["id"]]
            row["status"] = params["status"]
            row["sent_log_id"] = params["sent_log_id"]
            row["error"] = params["error"]
        elif "SELECT 1 FROM mail_rail_optouts" in sql:
            self._results = []
        elif "SELECT * FROM email_drafts WHERE id" in sql:
            row = self.db.rows.get(params["id"])
            if row:
                self._results = [self._shape(dict(row))]
        elif "FROM email_processing_registry" in sql:
            # bramka świeżości (_newer_inbound_from): w testach brak nowszej
            # poczty od adresata — fetchone() -> None
            self._results = []
        else:  # pragma: no cover - unexpected statement
            raise AssertionError(f"FakeDraftCursor: unhandled SQL: {sql[:120]}")

    def _shape(self, row: dict):
        if self.dict_rows:
            return row
        return (row["id"],)

    def fetchone(self):
        return self._results.pop(0) if self._results else None

    def fetchall(self):
        out, self._results = self._results, []
        return out


class _FakeConn:
    def __init__(self, db: _FakeDraftDb):
        self.db = db

    def cursor(self, cursor_factory=None):
        return _FakeDraftCursor(self.db, dict_rows=cursor_factory is not None)

    def close(self):
        pass


@pytest.fixture()
def draft_db():
    db = _FakeDraftDb()
    with mock.patch.object(mail_rail, "_connect", return_value=_FakeConn(db)):
        yield db


def test_create_draft_notifies_whatsapp_with_approval_format(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify,
        "send_whatsapp_dm",
        return_value={"ok": True, "message_id": "wa-1"},
    ) as wa:
        result = mail_rail.create_curated_draft(
            TO, "Temat testowy", "Treść.", company_id=30, created_by="orchestrator"
        )

    assert result == {"draft_id": 1, "status": "pending_approval"}
    row = draft_db.rows[1]
    assert row["status"] == "pending_approval"
    assert row["error"] is None
    assert row["from_address"] == "office@example.com"

    msg = wa.call_args[0][0]
    assert msg.startswith("[Digital Secretariat mail #1] Do zatwierdzenia: Temat testowy")
    assert f"→ {TO}" in msg
    assert "(firma 30)" in msg
    assert "TAK 1 / NIE 1 / TREŚĆ 1" in msg


def test_whatsapp_failure_does_not_fail_draft_creation(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify,
        "send_whatsapp_dm",
        return_value={"ok": False, "error": "bridge HTTP 503"},
    ):
        result = mail_rail.create_curated_draft(TO, "Temat", "Treść.")

    assert result == {"draft_id": 1, "status": "pending_approval"}
    row = draft_db.rows[1]
    assert row["status"] == "pending_approval"  # draft exists, nag catches it
    assert "bridge HTTP 503" in row["error"]


def test_release_draft_sends_once_and_double_release_is_guarded(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify, "send_whatsapp_dm", return_value={"ok": True}
    ):
        mail_rail.create_curated_draft(TO, "Temat", "Treść.", company_id=30)

    with (
        mock.patch.object(
            mail_rail.smtp_gateway,
            "send_email",
            return_value=SendResult(success=True, message_id="<m@x>"),
        ) as send,
        mock.patch.object(mail_rail, "_lookup_send_log_id", return_value=55),
    ):
        first = mail_rail.release_draft(1, via="whatsapp:TAK")
        second = mail_rail.release_draft(1, via="whatsapp:TAK")

    assert first["status"] == "sent"
    assert first["sent_log_id"] == 55
    assert draft_db.rows[1]["status"] == "sent"
    assert draft_db.rows[1]["sent_log_id"] == 55
    assert draft_db.rows[1]["decision_via"] == "whatsapp:TAK"

    # Double release: claim UPDATE matches no row -> error, NO second send
    assert second["status"] == "error"
    assert "status=sent" in second["detail"]
    send.assert_called_once()
    assert send.call_args.kwargs["automation_mode"] == "formatted_approved"
    assert send.call_args.kwargs["template_key"] is None


def test_failed_release_stays_retryable(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify, "send_whatsapp_dm", return_value={"ok": True}
    ):
        mail_rail.create_curated_draft(TO, "Temat", "Treść.")

    with mock.patch.object(
        mail_rail.smtp_gateway,
        "send_email",
        return_value=SendResult(success=False, error="SMTP down"),
    ):
        first = mail_rail.release_draft(1, via="whatsapp:TAK")

    assert first["status"] == "failed"
    assert draft_db.rows[1]["status"] == "failed"
    assert "SMTP down" in draft_db.rows[1]["error"]

    # After the fix, releasing again succeeds (failed -> claimable)
    with (
        mock.patch.object(
            mail_rail.smtp_gateway,
            "send_email",
            return_value=SendResult(success=True, message_id="<m2@x>"),
        ),
        mock.patch.object(mail_rail, "_lookup_send_log_id", return_value=56),
    ):
        retry = mail_rail.release_draft(1, via="cli")

    assert retry["status"] == "sent"
    assert draft_db.rows[1]["status"] == "sent"
    assert draft_db.rows[1]["sent_log_id"] == 56


def test_curated_release_honors_company_killswitch(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify, "send_whatsapp_dm", return_value={"ok": True}
    ):
        mail_rail.create_curated_draft(TO, "Temat", "Treść.", company_id=30)

    with (
        mock.patch.object(mail_rail, "_killswitch_active", return_value=True),
        mock.patch.object(mail_rail.smtp_gateway, "send_email") as send,
    ):
        result = mail_rail.release_draft(1, via="secretariat-board", expected_revision=0)

    assert result["status"] == "failed"
    assert result["reason"] == "killswitch"
    assert draft_db.rows[1]["status"] == "failed"
    send.assert_not_called()


def test_reject_draft_only_from_pending(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify, "send_whatsapp_dm", return_value={"ok": True}
    ):
        mail_rail.create_curated_draft(TO, "Temat", "Treść.")

    with mock.patch.object(mail_rail.smtp_gateway, "send_email") as send:
        result = mail_rail.reject_draft(1, via="whatsapp:NIE")
        again = mail_rail.reject_draft(1, via="whatsapp:NIE")

    assert result["status"] == "rejected"
    assert draft_db.rows[1]["status"] == "rejected"
    assert again["status"] == "error"
    assert "status=rejected" in again["detail"]
    send.assert_not_called()  # rejection never sends anything


def test_edit_draft_keeps_old_version_and_increments_revision(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify,
        "send_whatsapp_dm",
        return_value={"ok": True},
    ):
        mail_rail.create_curated_draft(TO, "Stary temat", "Stara treść.")

    result = mail_rail.edit_draft(
        1,
        subject="Nowy temat",
        body="Nowa treść.",
        via="secretariat-board:owner@example.com",
        expected_revision=0,
    )

    assert result["status"] == "pending_approval"
    assert result["revision_count"] == 1
    assert draft_db.rows[1]["subject"] == "Nowy temat"
    assert draft_db.rows[1]["revisions"] == [
        {
            "via": "secretariat-board:owner@example.com",
            "old_subject": "Stary temat",
            "old_body": "Stara treść.",
        }
    ]


def test_release_refuses_stale_revision_without_sending(draft_db):
    with mock.patch.object(
        mail_rail.whatsapp_notify,
        "send_whatsapp_dm",
        return_value={"ok": True},
    ):
        mail_rail.create_curated_draft(TO, "Temat", "Treść.")
    mail_rail.edit_draft(1, body="Nowsza treść.", expected_revision=0)

    with mock.patch.object(mail_rail.smtp_gateway, "send_email") as send:
        result = mail_rail.release_draft(
            1,
            via="secretariat-board:owner@example.com",
            expected_revision=0,
        )

    assert result["status"] == "error"
    assert result["reason"] == "stale_revision"
    assert draft_db.rows[1]["status"] == "pending_approval"
    send.assert_not_called()


# ---------------------------------------------------------------------------
# 7. create_reply_draft — kontrakt "krótka odpowiedź" (bead Digital Secretariat-ly05)
# ---------------------------------------------------------------------------

RID = "11111111-2222-3333-4444-555555555555"

SRC_ROW = {
    "id": RID,
    "message_id": "MSG123@example.com",
    "sender_email": "alex.taylor@example.com",
    "subject": "Hello — wersja pokazowa",
    "company_id": None,  # nowa relacja — poprawny NULL
    "in_reply_to": None,
    "references_header": "<A@x> <B@y>",
    "recipient_address": "support@example.com",
}

OWN_ACCOUNTS = [("support@example.com",), ("ksiegowosc@example.com",)]


class _FakeReplyConn:
    """Minimalny fake psycopg2: sekwencja zapytań create_reply_draft.
    Kolejność: SELECT rejestr (RealDict) → SELECT konta → SELECT dup."""

    def __init__(self, src_row=None, accounts=None, dup=None):
        self.src_row = src_row
        self.accounts = accounts if accounts is not None else list(OWN_ACCOUNTS)
        self.dup = dup
        self.autocommit = True
        self.committed = False
        self.rolled_back = False
        self._selects = 0

    def cursor(self, cursor_factory=None):
        conn = self

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                self._sql = " ".join(str(sql).split())

            def fetchone(self):
                if "FROM email_processing_registry" in self._sql:
                    return conn.src_row
                if "FROM email_drafts" in self._sql:
                    return conn.dup
                return None

            def fetchall(self):
                if "system_email_accounts" in self._sql:
                    return conn.accounts
                return []

        return _Cur()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def _reply(conn, body="Dziękujemy, potwierdzam spotkanie.", subject=None, insert_id=91):
    with (
        mock.patch.object(mail_rail, "_connect", return_value=conn),
        mock.patch.object(mail_rail, "_insert_draft", return_value=insert_id) as ins,
    ):
        out = mail_rail.create_reply_draft(RID, body, subject=subject, created_by="test")
    return out, ins


def test_reply_happy_path_maps_source_to_draft():
    conn = _FakeReplyConn(src_row=dict(SRC_ROW))
    out, ins = _reply(conn)
    assert out == {
        "draft_id": 91,
        "status": "pending_approval",
        "source_registry_id": RID,
        "revision_count": 0,
    }
    fields = ins.call_args[0][1]
    assert fields["to_address"] == "alex.taylor@example.com"
    assert fields["from_address"] == "support@example.com"
    assert fields["company_id"] is None  # NULL przechodzi
    assert fields["subject"] == "Re: Hello — wersja pokazowa"
    assert fields["in_reply_to"] == "<MSG123@example.com>"  # Angle brackets are normalized.
    assert fields["references_header"] == "<A@x> <B@y> <MSG123@example.com>"
    assert fields["log_category"] == "inbound_reply"
    assert conn.committed


def test_reply_subject_re_not_duplicated():
    row = dict(SRC_ROW, subject="Re: już z prefiksem")
    out, ins = _reply(_FakeReplyConn(src_row=row))
    assert ins.call_args[0][1]["subject"] == "Re: już z prefiksem"


def test_reply_invalid_uuid_is_source_not_found():
    with pytest.raises(mail_rail.MailRailError) as e:
        mail_rail.create_reply_draft("nie-uuid", "treść", created_by="test")
    assert e.value.code == "source_not_found"


def test_reply_missing_registry_row():
    with pytest.raises(mail_rail.MailRailError) as e:
        _reply(_FakeReplyConn(src_row=None))
    assert e.value.code == "source_not_found"


@pytest.mark.parametrize("body", ["", "   ", "x" * 10_001])
def test_reply_body_bounds(body):
    with pytest.raises(mail_rail.MailRailError) as e:
        mail_rail.create_reply_draft(RID, body, created_by="test")
    assert e.value.code == "invalid_body"


@pytest.mark.parametrize(
    "sender",
    [
        "no-reply@x.com",
        "noreply@x.com",  # no-reply
        "a@b.com,c@d.com",
        "zly@adres\r\n@e.com",  # lista / CRLF
        "",
        "bez-malpy",  # puste / bez @
        "support@example.com",  # własna aktywna skrzynka
    ],
)
def test_reply_sender_rejections(sender):
    row = dict(SRC_ROW, sender_email=sender)
    with pytest.raises(mail_rail.MailRailError) as e:
        _reply(_FakeReplyConn(src_row=row))
    assert e.value.code == "invalid_sender"


def test_reply_mailbox_unknown_and_unavailable():
    with pytest.raises(mail_rail.MailRailError) as e:
        _reply(_FakeReplyConn(src_row=dict(SRC_ROW, recipient_address=None)))
    assert e.value.code == "source_mailbox_unknown"

    row = dict(SRC_ROW, recipient_address="powiadomienia@example.com")
    with pytest.raises(mail_rail.MailRailError) as e:
        _reply(_FakeReplyConn(src_row=row))
    assert e.value.code == "source_mailbox_unavailable"


def test_reply_duplicate_returns_existing_draft():
    conn = _FakeReplyConn(src_row=dict(SRC_ROW), dup=(77, "pending_approval"))
    with pytest.raises(mail_rail.MailRailError) as e:
        _reply(conn)
    assert e.value.code == "reply_already_exists"
    assert e.value.draft_id == 77
    assert e.value.status == "pending_approval"


def test_reply_race_unique_violation_maps_to_conflict():
    import psycopg2.errors as pgerr

    conn = _FakeReplyConn(src_row=dict(SRC_ROW), dup=None)

    def boom(*a, **k):
        conn.dup = (78, "sent")  # równoległy zwycięzca widoczny po rollbacku
        raise pgerr.UniqueViolation()

    with (
        mock.patch.object(mail_rail, "_connect", return_value=conn),
        mock.patch.object(mail_rail, "_insert_draft", side_effect=boom),
    ):
        with pytest.raises(mail_rail.MailRailError) as e:
            mail_rail.create_reply_draft(RID, "treść", created_by="test")
    assert e.value.code == "reply_already_exists"
    assert e.value.draft_id == 78


# ---------------------------------------------------------------------------
# 8. release_draft — przelot wątku do SMTP + oznaczenie rejestru
# ---------------------------------------------------------------------------

REPLY_DRAFT_ROW = {
    "id": 91,
    "company_id": None,
    "from_address": "support@example.com",
    "to_address": "alex.taylor@example.com",
    "cc_addresses": None,
    "subject": "Re: Hello",
    "body": "Treść odpowiedzi.",
    "body_html": None,
    "attachments": None,
    "log_category": "inbound_reply",
    "source_registry_id": RID,
    "in_reply_to": "<MSG123@example.com>",
    "references_header": "<A@x> <B@y> <MSG123@example.com>",
}


def _release_with(send_result):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return send_result

    with (
        mock.patch.object(mail_rail, "_connect", return_value=mock.MagicMock()),
        mock.patch.object(mail_rail, "_claim_draft", return_value=dict(REPLY_DRAFT_ROW)),
        mock.patch.object(mail_rail, "_newer_inbound_from", return_value=None),
        mock.patch.object(mail_rail.smtp_gateway, "send_email", side_effect=fake_send),
        mock.patch.object(mail_rail, "_lookup_send_log_id", return_value=555),
        mock.patch.object(mail_rail, "_finalize_draft") as fin,
        mock.patch.object(mail_rail, "_mark_registry_replied") as marked,
    ):
        out = mail_rail.release_draft(91, via="test")
    return out, captured, fin, marked


def test_release_reply_threads_headers_to_gateway():
    out, sent, fin, marked = _release_with(SendResult(success=True, message_id="<out@example.com>"))
    assert out["status"] == "sent" and out["sent_log_id"] == 555
    assert sent["in_reply_to"] == "<MSG123@example.com>"
    assert sent["references"] == ["<A@x>", "<B@y>", "<MSG123@example.com>"]
    assert sent["from_account"] == "support@example.com"
    assert sent["approved_send"] is True
    fin.assert_called_once()
    assert fin.call_args[0][2] == "sent"
    marked.assert_called_once()
    assert marked.call_args[0][1] == RID  # rejestr oznaczony PO sukcesie


def test_release_reply_smtp_failure_no_fake_success():
    out, sent, fin, marked = _release_with(
        SendResult(success=False, error="SMTP 451 spróbuj później")
    )
    assert out["status"] == "failed"
    assert "sent_log_id" not in out or not out.get("sent_log_id")
    assert fin.call_args[0][2] == "failed"
    marked.assert_not_called()  # rejestr NIE oznaczony po porażce
