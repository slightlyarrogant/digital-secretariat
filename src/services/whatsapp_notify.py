"""
Minimal WhatsApp DM notifier via the local hermes bridge.

Sibling of ``scripts/utils/admin_alert.py::_send_whatsapp`` — the same POST
against the same bridge, kept deliberately identical in shape (unification
into one shared transport module is a later cleanup). This module exists so
``src/services`` code (mail_rail) does not import from ``scripts/``.

Contract (mirrors admin_alert):
- Never raises. Returns {"ok": bool, "error": ..., "message_id": ...}.
- The bridge answers 503 when not connected to WhatsApp and returns
  {"success": true} only after an awaited real send — a genuine
  deliverability signal.
"""

import logging
import os

logger = logging.getLogger(__name__)

WHATSAPP_BRIDGE_URL = os.getenv("SECRETARIAT_WHATSAPP_BRIDGE_URL", "").strip()
ADMIN_WHATSAPP_JID = os.getenv("SECRETARIAT_WHATSAPP_JID", "").strip()
WHATSAPP_HTTP_TIMEOUT = 30  # bridge awaits the actual send
WHATSAPP_BODY_LIMIT = 1500


def send_whatsapp_dm(
    message: str,
    jid: str | None = None,
    timeout: int = WHATSAPP_HTTP_TIMEOUT,
) -> dict:
    """Send a WhatsApp DM via the local hermes bridge. Never raises.

    Returns:
        {"ok": True, "message_id": ...} on confirmed delivery,
        {"ok": False, "error": ...} otherwise.
    """
    target = (jid or ADMIN_WHATSAPP_JID).strip()
    if not WHATSAPP_BRIDGE_URL or not target:
        return {"ok": False, "error": "WhatsApp notifier is not configured"}

    try:
        import requests

        body = message
        if len(body) > WHATSAPP_BODY_LIMIT:
            body = body[:WHATSAPP_BODY_LIMIT] + "\n[...skrócono]"

        r = requests.post(
            f"{WHATSAPP_BRIDGE_URL}/send",
            json={"chatId": target, "message": body},
            timeout=timeout,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"bridge HTTP {r.status_code}: {r.text[:200]}"}
        payload = r.json()
        if not payload.get("success"):
            return {"ok": False, "error": f"bridge reported failure: {str(payload)[:200]}"}
        return {"ok": True, "message_id": payload.get("messageId")}
    except Exception as exc:  # noqa: BLE001 — notify must never break the caller
        return {"ok": False, "error": f"bridge request failed: {exc}"}
