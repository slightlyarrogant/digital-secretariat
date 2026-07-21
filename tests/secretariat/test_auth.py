from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.secretariat.auth import require_tailnet_principal


def _request(host: str = "127.0.0.1") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_auth_fails_closed_without_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRETARIAT_ALLOWED_LOGINS", raising=False)

    with pytest.raises(HTTPException) as exc:
        require_tailnet_principal(_request(), login="owner@example.com")  # type: ignore[arg-type]

    assert exc.value.status_code == 503


def test_auth_rejects_untrusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")

    with pytest.raises(HTTPException) as exc:
        require_tailnet_principal(  # type: ignore[arg-type]
            _request("100.64.0.10"), login="owner@example.com"
        )

    assert exc.value.status_code == 403


def test_auth_requires_tailnet_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")

    with pytest.raises(HTTPException) as exc:
        require_tailnet_principal(_request(), login=None)  # type: ignore[arg-type]

    assert exc.value.status_code == 401


def test_auth_allows_normalized_allowlisted_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "Owner@Example.com")

    principal = require_tailnet_principal(  # type: ignore[arg-type]
        _request(), login=" owner@example.com ", display_name="Owner"
    )

    assert principal.login == "owner@example.com"
    assert principal.display_name == "Owner"
