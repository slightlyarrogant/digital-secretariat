from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from src.secretariat.database import (
    SecretariatDatabaseError,
    _read_database_url,
    _read_rls_user_id,
    configure_read_only_session,
)


def test_database_url_uses_systemd_credential_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credential = tmp_path / "database-url"
    credential.write_text("postgresql://file-reader@localhost/database\n", encoding="utf-8")
    monkeypatch.setenv("SECRETARIAT_DATABASE_URL_FILE", str(credential))
    monkeypatch.setenv("DATABASE_URL", "postgresql://environment-reader@localhost/database")

    assert _read_database_url() == "postgresql://file-reader@localhost/database"


def test_database_url_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRETARIAT_DATABASE_URL_FILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://local-reader@localhost/database")

    assert _read_database_url() == "postgresql://local-reader@localhost/database"


def test_database_url_fails_closed_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRETARIAT_DATABASE_URL_FILE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SecretariatDatabaseError, match="not configured"):
        _read_database_url()


def test_database_url_hides_credential_file_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("SECRETARIAT_DATABASE_URL_FILE", str(missing))

    with pytest.raises(SecretariatDatabaseError, match="credential is unreadable") as error:
        _read_database_url()

    assert str(missing) not in str(error.value)


@pytest.mark.parametrize("value", ["", "0", "-1", "owner", "1.5"])
def test_rls_user_id_rejects_invalid_values(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRETARIAT_RLS_USER_ID", value)

    with pytest.raises(SecretariatDatabaseError, match="RLS user is not configured"):
        _read_rls_user_id()


def test_read_only_session_sets_transaction_and_owner_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_RLS_USER_ID", "12")
    session = Mock(spec=Session)

    configure_read_only_session(session)

    calls = session.execute.call_args_list
    assert str(calls[0].args[0]) == "SET TRANSACTION READ ONLY"
    assert "set_config('app.current_user_id'" in str(calls[1].args[0])
    assert calls[1].args[1] == {"user_id": "12"}
