"""
Regression guard for outbound email From-header validity.

Background
---------
On 2026-06-10 a reminder from ksiegowosc@example.com bounced at Gmail with
`550-5.7.1 Messages missing a valid address in From: header`. The cause was a
sender that built the From header by bare string formatting, which can emit an
empty / malformed address.

All outbound senders now build their MIME message through
`src.services.email_headers.apply_standard_headers`, which GUARANTEES a valid
From (and Message-ID + Date) or raises `MissingFromAddressError`. These tests
fail loudly if that guarantee regresses.

No network / SMTP is touched — these are pure header-construction tests.
"""

import re
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr

import pytest

from src.services.email_headers import (
    MissingFromAddressError,
    apply_standard_headers,
    build_from_header,
)


class TestBuildFromHeader:
    """The From header must always contain a real address."""

    def test_name_and_address(self):
        value = build_from_header("ksiegowosc@example.com", "Krystyna")
        assert value == "Krystyna <ksiegowosc@example.com>"
        # parseaddr must extract a non-empty address with an '@'
        _name, addr = parseaddr(value)
        assert addr == "ksiegowosc@example.com"

    def test_bare_address_is_valid(self):
        value = build_from_header("faktury@example.com")
        _name, addr = parseaddr(value)
        assert addr == "faktury@example.com"

    def test_unicode_display_name_is_encoded(self):
        value = build_from_header("ksiegowosc@example.com", "Księgowość Krystyna")
        _name, addr = parseaddr(value)
        # Address must remain intact regardless of display-name encoding
        assert addr == "ksiegowosc@example.com"

    @pytest.mark.parametrize("bad", ["", "   ", None, "Krystyna", "no-at-sign"])
    def test_invalid_address_raises(self, bad):
        # This is the exact 550-5.7.1 trigger — must never silently produce a header.
        with pytest.raises(MissingFromAddressError):
            build_from_header(bad, "Krystyna")


class TestApplyStandardHeaders:
    """Every message stamped by the shared builder carries the mandatory headers."""

    def _msg(self):
        m = MIMEMultipart("alternative")
        m["To"] = "recipient@example.com"
        return m

    def test_sets_from_message_id_and_date(self):
        msg = self._msg()
        apply_standard_headers(
            msg,
            from_address="ksiegowosc@example.com",
            from_name="Krystyna",
            subject="Ponaglenie",
        )

        # From: present, non-empty, parseable to a real address
        assert msg["From"], "From header must be set"
        _name, addr = parseaddr(msg["From"])
        assert addr == "ksiegowosc@example.com"
        assert "@" in addr

        # Message-ID present and well-formed (<...@domain>)
        assert msg["Message-ID"]
        assert re.match(r"^<[^>]+@[^>]+>$", msg["Message-ID"].strip())

        # Date present
        assert msg["Date"]

        # Subject set when none existed
        assert msg["Subject"] == "Ponaglenie"

    def test_message_id_uses_sender_domain(self):
        msg = self._msg()
        apply_standard_headers(msg, from_address="faktury@example.com", from_name="Faktury")
        assert "example.com" in msg["Message-ID"]

    def test_existing_message_id_and_date_preserved(self):
        msg = self._msg()
        msg["Message-ID"] = "<original-thread-id@example.com>"
        msg["Date"] = "Mon, 09 Jun 2026 10:00:00 +0200"
        apply_standard_headers(msg, from_address="support@example.com", from_name="Krystyna")
        assert msg["Message-ID"] == "<original-thread-id@example.com>"
        assert msg["Date"] == "Mon, 09 Jun 2026 10:00:00 +0200"

    def test_existing_subject_preserved(self):
        msg = self._msg()
        msg["Subject"] = "Already set"
        apply_standard_headers(
            msg, from_address="support@example.com", from_name="Krystyna", subject="Ignored"
        )
        assert msg["Subject"] == "Already set"

    @pytest.mark.parametrize("bad", ["", None, "not-an-address"])
    def test_blank_from_raises_before_send(self, bad):
        # The regression guard: a message that would bounce at Gmail must never be built.
        msg = self._msg()
        with pytest.raises(MissingFromAddressError):
            apply_standard_headers(msg, from_address=bad, from_name="Krystyna")
