"""Isolated database session factory for the Secretariat."""

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class SecretariatDatabaseError(RuntimeError):
    """Database configuration is absent or cannot be used safely."""


def _read_database_url() -> str:
    credential_path = os.getenv("SECRETARIAT_DATABASE_URL_FILE")
    if credential_path:
        try:
            database_url = Path(credential_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretariatDatabaseError("Secretariat database credential is unreadable") from exc
    else:
        database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise SecretariatDatabaseError("Secretariat database credential is not configured")
    return database_url


def _read_rls_user_id() -> str:
    user_id = os.getenv("SECRETARIAT_RLS_USER_ID", "").strip()
    if not user_id.isdecimal() or int(user_id) < 1:
        raise SecretariatDatabaseError("Secretariat RLS user is not configured")
    return user_id


def configure_read_only_session(session: Session) -> None:
    """Start a read-only transaction with the existing owner RLS context."""
    session.execute(text("SET TRANSACTION READ ONLY"))
    session.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, true), "
            "set_config('app.is_superuser', 'true', true)"
        ),
        {"user_id": _read_rls_user_id()},
    )


@lru_cache(maxsize=2)
def _session_maker(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
        class_=Session,
    )


def create_session() -> Session:
    return _session_maker(_read_database_url())()
