"""Measurement provenance tests for the audited SMTP gateway."""

from unittest import mock

from src.services import smtp_gateway


def test_log_send_persists_automation_provenance() -> None:
    session = mock.MagicMock()
    session_context = mock.MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    with mock.patch.object(smtp_gateway, "SessionLocal", return_value=session_context):
        smtp_gateway._log_send(
            "ksiegowosc@example.com",
            "client@example.com",
            "Dokumenty",
            "<p>Treść</p>",
            smtp_gateway.SendResult(success=True, message_id="<outbound@example.com>"),
            in_reply_to="<inbound@example.com>",
            sent_by="mail_rail:missing_bank_statement",
            automation_mode="automatic_template",
            template_key="missing_bank_statement",
            template_version="a" * 64,
        )

    parameters = session.execute.call_args.args[1]
    assert parameters["reply_to"] == "<inbound@example.com>"
    assert parameters["automation_mode"] == "automatic_template"
    assert parameters["template_key"] == "missing_bank_statement"
    assert parameters["template_version"] == "a" * 64
    session.commit.assert_called_once_with()
