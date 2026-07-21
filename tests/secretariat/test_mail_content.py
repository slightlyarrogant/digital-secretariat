from email.message import EmailMessage
from typing import Any

from src.secretariat.mail_content import _fetch, _write_content_index, read_cached_message
from src.secretariat.schemas import MessageContent


def test_cached_message_returns_plain_text_and_attachment_metadata(tmp_path, monkeypatch) -> None:
    registry_id = "00000000-0000-0000-0000-000000000001"
    directory = tmp_path / registry_id
    directory.mkdir()
    message = EmailMessage()
    message["From"] = "Client <client@example.com>"
    message["To"] = "faktury@example.com"
    message["Subject"] = "Faktura za czerwiec"
    message.set_content("Dzień dobry, faktura jest w załączniku.")
    message.add_attachment(
        b"pdf-content",
        maintype="application",
        subtype="pdf",
        filename="FV-06.pdf",
    )
    (directory / "raw.eml").write_bytes(message.as_bytes())
    (directory / "meta.json").write_text(
        '{"mailbox":"faktury@example.com","folder":"INBOX.Processed"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("SECRETARIAT_MAIL_CACHE", str(tmp_path))

    result = read_cached_message(registry_id)

    assert result.available is True
    assert result.mailbox == "faktury@example.com"
    assert result.body_text == "Dzień dobry, faktura jest w załączniku."
    assert result.attachments[0].filename == "FV-06.pdf"
    assert result.attachments[0].size_bytes == len(b"pdf-content")


def test_cached_message_never_uses_registry_id_as_a_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SECRETARIAT_MAIL_CACHE", str(tmp_path))

    result = read_cached_message("../../etc/passwd")

    assert result.available is False
    assert list(tmp_path.iterdir()) == []


def test_cached_message_prefers_private_content_index(tmp_path, monkeypatch) -> None:
    registry_id = "00000000-0000-0000-0000-000000000003"
    directory = tmp_path / registry_id
    directory.mkdir()
    (directory / "raw.eml").write_text("not a usable fallback", encoding="utf-8")
    _write_content_index(
        directory,
        MessageContent(
            registry_id=registry_id,
            available=True,
            subject="Indeksowany mail",
            body_text="Treść gotowa do szybkiego podglądu.",
        ),
    )
    monkeypatch.setenv("SECRETARIAT_MAIL_CACHE", str(tmp_path))

    result = read_cached_message(registry_id)

    assert result.available is True
    assert result.subject == "Indeksowany mail"
    assert result.body_text == "Treść gotowa do szybkiego podglądu."
    assert (directory / "content.json").stat().st_mode & 0o777 == 0o600


def test_cached_html_is_rendered_as_text_not_active_markup(tmp_path, monkeypatch) -> None:
    registry_id = "00000000-0000-0000-0000-000000000002"
    directory = tmp_path / registry_id
    directory.mkdir()
    message = EmailMessage()
    message["Subject"] = "HTML"
    message.set_content("<p>Treść</p><script>alert(1)</script>", subtype="html")
    (directory / "raw.eml").write_bytes(message.as_bytes())
    (directory / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SECRETARIAT_MAIL_CACHE", str(tmp_path))

    result = read_cached_message(registry_id)

    assert result.body_text == "Treść"
    assert "script" not in result.body_text


def test_imap_fetch_uses_read_only_select_and_body_peek(monkeypatch) -> None:
    calls: list[tuple[str, Any]] = []

    class FakeImap:
        def __init__(self, _host: str, _port: int, *, timeout: int) -> None:
            assert timeout == 30

        def login(self, _username: str, _password: str) -> None:
            return None

        def select(self, folder: str, *, readonly: bool) -> tuple[str, list[bytes]]:
            calls.append(("select", (folder, readonly)))
            return "OK", [b"1"]

        def search(self, *_args: str) -> tuple[str, list[bytes]]:
            return "OK", [b"7"]

        def fetch(self, _sequence: bytes, query: str) -> tuple[str, list[tuple[bytes, bytes]]]:
            calls.append(("fetch", query))
            return "OK", [(b"7", b"Subject: Test\r\n\r\nBody")]

        def logout(self) -> None:
            return None

    monkeypatch.setattr("src.secretariat.mail_content.imaplib.IMAP4_SSL", FakeImap)

    result = _fetch(
        {
            "host": "imap.example.com",
            "port": 993,
            "username": "reader",
            "password": "secret",
        },
        "<message@example.com>",
    )

    assert result is not None
    assert calls[0] == ("select", ('"INBOX"', True))
    assert calls[1] == ("fetch", "(BODY.PEEK[])")
