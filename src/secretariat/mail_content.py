"""Private cache and read-only IMAP archiver for message previews."""

from __future__ import annotations

import argparse
import email
import html
import imaplib
import json
import os
import re
import uuid
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from typing import Any

import psycopg2  # type: ignore[import-untyped]

from src.secretariat.schemas import MessageAttachment, MessageContent

_FOLDERS = ("INBOX", "INBOX.Processed", "Processed")
_BODY_LIMIT = 20_000
_CONTENT_FILENAME = "content.json"
_PIPELINES = {
    "email_machine_mcp": "email_machine_with_mcp",
    "email_machine": "email_machine",
    "ocr_extraction": "ocr_extraction",
}


def _cache_root() -> Path:
    return Path(
        os.getenv(
            "SECRETARIAT_MAIL_CACHE",
            "/var/cache/digital-secretariat-mail",
        )
    )


def _database_url() -> str:
    credential = os.getenv("SECRETARIAT_CONTENT_DATABASE_URL_FILE", "").strip()
    if not credential:
        raise RuntimeError("Content reader database credential is not configured")
    try:
        value = Path(credential).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("Content reader database credential is unreadable") from exc
    if not value:
        raise RuntimeError("Content reader database credential is empty")
    return value


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _plain_text(message: Message) -> str:
    plain: str | None = None
    rich: str | None = None
    for part in message.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        if part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type not in {"text/plain", "text/html"}:
            continue
        decoded = part.get_payload(decode=True)
        payload = decoded if isinstance(decoded, bytes) else b""
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if content_type == "text/plain" and plain is None:
            plain = text
        elif content_type == "text/html" and rich is None:
            rich = text
    value = plain if plain is not None else _html_to_text(rich or "")
    value = value.strip()
    return value[:_BODY_LIMIT] + ("\n[treść skrócona]" if len(value) > _BODY_LIMIT else "")


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"[ \t]+", " ", value)


def _attachments(message: Message) -> list[MessageAttachment]:
    attachments: list[MessageAttachment] = []
    for index, part in enumerate(message.walk(), start=1):
        filename = part.get_filename()
        if part.get_content_disposition() != "attachment" and filename is None:
            continue
        decoded = part.get_payload(decode=True)
        payload = decoded if isinstance(decoded, bytes) else b""
        attachments.append(
            MessageAttachment(
                filename=_decode(filename) or f"załącznik-{index}",
                content_type=part.get_content_type(),
                size_bytes=len(payload),
            )
        )
    return attachments


def _parse_cached_message(directory: Path, registry_id: str) -> MessageContent:
    raw_path = directory / "raw.eml"
    if not raw_path.is_file():
        return MessageContent(registry_id=registry_id, available=False)

    try:
        message = email.message_from_bytes(raw_path.read_bytes())
        metadata = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MessageContent(registry_id=registry_id, available=False)

    return MessageContent(
        registry_id=registry_id,
        available=True,
        mailbox=metadata.get("mailbox"),
        folder=metadata.get("folder"),
        from_address=_decode(message.get("From")),
        to_address=_decode(message.get("To")),
        sent_at=(message.get("Date") or "").strip() or None,
        subject=_decode(message.get("Subject")) or "(bez tematu)",
        body_text=_plain_text(message),
        attachments=_attachments(message),
    )


def _write_content_index(directory: Path, content: MessageContent) -> None:
    temporary = directory / f"{_CONTENT_FILENAME}.tmp"
    temporary.write_text(content.model_dump_json(), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(directory / _CONTENT_FILENAME)


def read_cached_message(registry_id: str) -> MessageContent:
    try:
        normalized_id = str(uuid.UUID(registry_id))
    except (ValueError, TypeError, AttributeError):
        return MessageContent(registry_id=str(registry_id), available=False)

    directory = _cache_root() / normalized_id
    content_path = directory / _CONTENT_FILENAME
    try:
        content = MessageContent.model_validate_json(content_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        content = _parse_cached_message(directory, normalized_id)
    if content.registry_id != normalized_id:
        return MessageContent(registry_id=normalized_id, available=False)
    return content


def _accounts(connection: Any) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT email_address, imap_host, imap_port, imap_username,
                   imap_password, processing_pipeline
            FROM system_email_accounts
            WHERE is_active = true
            ORDER BY id
            """
        )
        return [
            {
                "mailbox": row[0],
                "host": row[1],
                "port": row[2],
                "username": row[3],
                "password": row[4],
                "pipeline": row[5],
            }
            for row in cursor.fetchall()
        ]


def _registry_rows(connection: Any, limit: int) -> list[tuple[str, str, str | None]]:
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            """
            SELECT id::text, message_id, email_type
            FROM email_processing_registry
            ORDER BY COALESCE(received_at, created_at) DESC
            LIMIT %s
            """,
            (max(1, min(limit, 500)),),
        )
        return [(row[0], row[1], row[2]) for row in cursor.fetchall()]


def _fetch(account: dict[str, Any], message_id: str) -> tuple[bytes, str] | None:
    core = message_id.strip().strip("<>").strip()
    if not core or '"' in core:
        return None
    client = imaplib.IMAP4_SSL(account["host"], account["port"], timeout=30)
    try:
        client.login(account["username"], account["password"])
        for folder in _FOLDERS:
            try:
                status, _ = client.select(f'"{folder}"', readonly=True)
            except imaplib.IMAP4.error:
                continue
            if status != "OK":
                continue
            status, matches = client.search(None, "HEADER", "Message-ID", f'"{core}"')
            if status != "OK" or not matches or not matches[0]:
                continue
            status, fetched = client.fetch(matches[0].split()[0], "(BODY.PEEK[])")
            if status != "OK":
                continue
            for part in fetched:
                if isinstance(part, tuple) and len(part) > 1 and part[1]:
                    return bytes(part[1]), folder
        return None
    finally:
        try:
            client.logout()
        except Exception:
            pass


def cache_messages(limit: int = 200) -> dict[str, int]:
    root = _cache_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    connection = psycopg2.connect(_database_url(), connect_timeout=8)
    try:
        rows = _registry_rows(connection, limit)
        accounts = _accounts(connection)
    finally:
        connection.rollback()
        connection.close()

    cached = skipped = missing = failed = 0
    for registry_id, message_id, email_type in rows:
        directory = root / registry_id
        raw_path = directory / "raw.eml"
        if raw_path.is_file():
            content_path = directory / _CONTENT_FILENAME
            if not content_path.is_file():
                content = _parse_cached_message(directory, registry_id)
                if content.available:
                    _write_content_index(directory, content)
            skipped += 1
            continue
        preferred_pipeline = _PIPELINES.get(email_type or "", email_type)
        ordered = sorted(accounts, key=lambda item: item["pipeline"] != preferred_pipeline)
        found: tuple[bytes, str, str] | None = None
        for account in ordered:
            try:
                result = _fetch(account, message_id)
            except (OSError, imaplib.IMAP4.error):
                failed += 1
                continue
            if result is not None:
                raw, folder = result
                found = raw, str(account["mailbox"]), folder
                break
        if found is None:
            missing += 1
            continue
        raw, mailbox, folder = found
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = directory / "raw.eml.tmp"
        temporary.write_bytes(raw)
        temporary.chmod(0o600)
        temporary.replace(raw_path)
        metadata = directory / "meta.json"
        metadata.write_text(
            json.dumps({"mailbox": mailbox, "folder": folder}),
            encoding="utf-8",
        )
        metadata.chmod(0o600)
        content = _parse_cached_message(directory, registry_id)
        if content.available:
            _write_content_index(directory, content)
        cached += 1
    return {"cached": cached, "skipped": skipped, "missing": missing, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive message previews from IMAP")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    result = cache_messages(args.limit)
    print(" ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
