"""Minimal synchronous database factory for the reference mail-rail adapter."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


def _database_url() -> str:
    credential_file = os.getenv("DATABASE_URL_FILE", "").strip()
    if credential_file:
        return Path(credential_file).read_text(encoding="utf-8").strip()
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL_FILE or DATABASE_URL is required")
    return value


@lru_cache(maxsize=1)
def _engine() -> Engine:
    return create_engine(_database_url(), pool_pre_ping=True, future=True)


def SessionLocal() -> Session:
    """Open a session only when the adapter actually performs an action."""

    return Session(bind=_engine(), autoflush=False, expire_on_commit=False)
