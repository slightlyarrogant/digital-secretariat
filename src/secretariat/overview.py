"""Read-only operational projection over the existing source-of-truth tables."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.secretariat.database import configure_read_only_session
from src.secretariat.schemas import (
    ApprovalSummary,
    CaseSummary,
    CoverageSummary,
    FreshnessSummary,
    GuestSummary,
    InboundSummary,
    OperationalOverview,
)

REQUIRED_RELATIONS = (
    "companies",
    "client_registry",
    "client_obligations",
    "email_processing_registry",
    "email_drafts",
    "email_send_log",
    "guest_register",
    "client_registry_v",
)


class OverviewRepository(Protocol):
    def missing_relations(self) -> list[str]: ...

    def read(self, now: datetime) -> OperationalOverview: ...


_OVERVIEW_SQL = text(
    """
    SELECT
        (SELECT count(id) FROM companies) AS companies,
        (SELECT count(id) FROM client_registry) AS registered_clients,
        (SELECT count(id) FROM email_processing_registry
         WHERE COALESCE(received_at, created_at) >= :window_started_at) AS inbound_received,
        (SELECT count(id) FROM email_processing_registry
         WHERE COALESCE(received_at, created_at) >= :window_started_at
           AND company_id IS NULL) AS inbound_unmatched,
        (SELECT count(id) FROM email_processing_registry
         WHERE COALESCE(received_at, created_at) >= :window_started_at
           AND processing_status = 'failed') AS inbound_failed,
        (SELECT count(id) FROM client_obligations WHERE status = 'open') AS cases_open,
        (SELECT count(id) FROM client_obligations
         WHERE status = 'open' AND due_date < :today) AS cases_overdue,
        (SELECT count(id) FROM client_obligations
         WHERE status = 'open' AND due_date BETWEEN :today AND :due_horizon) AS cases_due_7d,
        (SELECT count(id) FROM client_obligations
         WHERE status = 'open' AND (owner IS NULL OR due_date IS NULL)) AS cases_missing_controls,
        (SELECT count(id) FROM email_drafts
         WHERE status IN ('pending_approval', 'pending', 'waiting')) AS approvals_pending,
        (SELECT count(id) FROM email_drafts
         WHERE status IN ('pending_approval', 'pending', 'waiting')
           AND due_at IS NOT NULL AND due_at < :now) AS approvals_overdue,
        (SELECT count(id) FROM email_drafts WHERE status = 'failed') AS approvals_failed,
        (SELECT count(id) FROM guest_register
         WHERE stage NOT IN ('klient', 'odpadl')) AS guests_active,
        (SELECT count(id) FROM guest_register
         WHERE stage NOT IN ('klient', 'odpadl') AND next_action_due < :today) AS guests_overdue,
        (SELECT count(id) FROM guest_register
         WHERE stage NOT IN ('klient', 'odpadl')
           AND (next_action IS NULL OR next_action_owner IS NULL OR next_action_due IS NULL)
        ) AS guests_incomplete,
        (SELECT max(COALESCE(received_at, created_at))
         FROM email_processing_registry) AS last_inbound_at,
        (SELECT max(sent_at) FROM email_send_log) AS last_send_attempt_at
    """
)


class PostgresOverviewRepository:
    """PostgreSQL adapter; every transaction is explicitly read-only."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def missing_relations(self) -> list[str]:
        session = self._session_factory()
        try:
            configure_read_only_session(session)
            rows = session.execute(
                text(
                    "SELECT relation_name FROM unnest(CAST(:relations AS text[])) relation_name "
                    "WHERE to_regclass('public.' || relation_name) IS NULL ORDER BY relation_name"
                ),
                {"relations": list(REQUIRED_RELATIONS)},
            )
            return [str(row.relation_name) for row in rows]
        finally:
            session.rollback()
            session.close()

    def read(self, now: datetime) -> OperationalOverview:
        session = self._session_factory()
        try:
            configure_read_only_session(session)
            return _read_overview(session, now)
        finally:
            session.rollback()
            session.close()


def _read_overview(session: Session, now: datetime) -> OperationalOverview:
    window_started_at = now - timedelta(hours=24)
    row = (
        session.execute(
            _OVERVIEW_SQL,
            {
                "now": now,
                "today": now.date(),
                "due_horizon": now.date() + timedelta(days=7),
                "window_started_at": window_started_at,
            },
        )
        .mappings()
        .one()
    )
    return _overview_from_row(row, now, window_started_at)


def _count(row: Any, key: str) -> int:
    value = row[key]
    return int(value or 0)


def _overview_from_row(row: Any, now: datetime, window_started_at: datetime) -> OperationalOverview:
    return OperationalOverview(
        generated_at=now,
        window_started_at=window_started_at,
        coverage=CoverageSummary(
            companies=_count(row, "companies"),
            registered_clients=_count(row, "registered_clients"),
        ),
        inbound=InboundSummary(
            received=_count(row, "inbound_received"),
            unmatched=_count(row, "inbound_unmatched"),
            failed=_count(row, "inbound_failed"),
        ),
        cases=CaseSummary(
            open=_count(row, "cases_open"),
            overdue=_count(row, "cases_overdue"),
            due_within_7_days=_count(row, "cases_due_7d"),
            missing_controls=_count(row, "cases_missing_controls"),
        ),
        approvals=ApprovalSummary(
            pending=_count(row, "approvals_pending"),
            overdue=_count(row, "approvals_overdue"),
            failed=_count(row, "approvals_failed"),
        ),
        guests=GuestSummary(
            active=_count(row, "guests_active"),
            overdue=_count(row, "guests_overdue"),
            incomplete=_count(row, "guests_incomplete"),
        ),
        freshness=FreshnessSummary(
            last_inbound_at=row["last_inbound_at"],
            last_send_attempt_at=row["last_send_attempt_at"],
        ),
    )
