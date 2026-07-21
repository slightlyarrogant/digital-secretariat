"""
Shared email-header builder for ALL outbound SMTP senders.

Single source of truth that guarantees every outgoing message carries the
three headers Gmail (and RFC 5322) require, so messages are never silently
rejected with `550-5.7.1 Messages missing a valid address in From: header`:

    1. From       — always `Display Name <address@domain>` (email.utils.formataddr)
    2. Message-ID — generated against the sender domain if absent
    3. Date       — RFC 2822 localtime if absent

WHY THIS EXISTS
---------------
An outbound message once bounced at Gmail because a sender built the From
header by bare string formatting
(`f"{name} <{addr}>"`), which can emit an empty / malformed address when the
address is missing. Routing every sender through `apply_standard_headers()`
makes that class of bug impossible: a blank from-address now raises loudly at
build time instead of producing a message Gmail rejects after the fact.

Usage (in any sender, after the MIME tree is assembled):

    from src.services.email_headers import apply_standard_headers

    apply_standard_headers(
        msg,
        from_address="office@example.com",
        from_name="Company Office",
        subject=subject,
    )

The from-address must come from the caller's existing config / DB
(system_email_accounts, sops mailbox_secrets, settings) — this helper never
hardcodes an address.
"""

from __future__ import annotations

from email.message import Message
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional

# Domain used for generated Message-IDs when the from-address has no usable host.
_DEFAULT_MSGID_DOMAIN = "localhost"


class MissingFromAddressError(ValueError):
    """Raised when a message would be sent without a usable From address."""


def build_from_header(from_address: str, from_name: Optional[str] = None) -> str:
    """
    Build a valid RFC 5322 From header value: `Display Name <addr@domain>`.

    Args:
        from_address: Sender email address. Must be a non-empty string that
                      looks like an address (contains '@'). This is the field
                      Gmail validates — a blank value triggers 550-5.7.1.
        from_name:    Optional display name. When falsy, a bare address is
                      produced (still RFC-valid), but a name is preferred.

    Returns:
        Header value safe to assign to msg["From"].

    Raises:
        MissingFromAddressError: If from_address is empty or not an address.
    """
    addr = (from_address or "").strip()
    if not addr or "@" not in addr:
        raise MissingFromAddressError(
            f"Refusing to build email with invalid From address: {from_address!r}. "
            "A valid 'address@domain' is required (Gmail rejects empty From with 550-5.7.1)."
        )
    # formataddr correctly quotes/encodes the display name and angle-brackets the address.
    return formataddr(((from_name or "").strip(), addr))


def apply_standard_headers(
    msg: Message,
    from_address: str,
    from_name: Optional[str] = None,
    subject: Optional[str] = None,
) -> Message:
    """
    Stamp the mandatory headers on an already-built MIME message in place.

    Always sets a valid From. Sets Message-ID and Date only if absent, so
    senders that already manage threading/Message-ID keep their value.

    Args:
        msg:          The MIME message (headers may be partially set already).
        from_address: Sender address from existing config/DB (never hardcoded here).
        from_name:    Optional display name.
        subject:      Optional subject — set only if not already present.

    Returns:
        The same `msg`, mutated, for convenience.

    Raises:
        MissingFromAddressError: If from_address is invalid (fail fast — never
            ship a message Gmail will bounce).
    """
    # From — always (re)set to the validated, properly-encoded value.
    from_value = build_from_header(from_address, from_name)
    if "From" in msg:
        msg.replace_header("From", from_value)
    else:
        msg["From"] = from_value

    # Subject — only if caller asked and none present.
    if subject is not None and "Subject" not in msg:
        msg["Subject"] = subject

    # Date — RFC 2822, localtime — only if missing.
    if "Date" not in msg:
        msg["Date"] = formatdate(localtime=True)

    # Message-ID — only if missing. Prefer the sender's own domain.
    if "Message-ID" not in msg:
        domain = _DEFAULT_MSGID_DOMAIN
        addr = (from_address or "").strip()
        if "@" in addr:
            host = addr.rsplit("@", 1)[1].strip()
            if host:
                domain = host
        msg["Message-ID"] = make_msgid(domain=domain)

    return msg
