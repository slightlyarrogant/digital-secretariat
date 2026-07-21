"""Fail-closed authentication at the Tailscale Serve trust boundary."""

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, Request, status


@dataclass(frozen=True)
class TailnetPrincipal:
    login: str
    display_name: str | None


def _csv_env(name: str, default: str = "") -> set[str]:
    return {item.strip().casefold() for item in os.getenv(name, default).split(",") if item.strip()}


def require_tailnet_principal(
    request: Request,
    login: Annotated[str | None, Header(alias="Tailscale-User-Login")] = None,
    display_name: Annotated[str | None, Header(alias="Tailscale-User-Name")] = None,
) -> TailnetPrincipal:
    """Accept identity headers only from the local Tailscale Serve proxy.

    The app is also required to bind to loopback. The proxy check prevents a
    caller from supplying Tailscale identity headers directly if that binding
    is accidentally changed later.
    """

    allowed_logins = _csv_env("SECRETARIAT_ALLOWED_LOGINS")
    if not allowed_logins:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secretariat access is not configured",
        )

    trusted_proxies = _csv_env("SECRETARIAT_TRUSTED_PROXY_IPS", "127.0.0.1,::1")
    client_host = request.client.host.casefold() if request.client else ""
    if client_host not in trusted_proxies:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted proxy")

    if not login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tailnet identity is required",
        )

    normalized_login = login.strip().casefold()
    if normalized_login not in allowed_logins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return TailnetPrincipal(login=normalized_login, display_name=display_name)
