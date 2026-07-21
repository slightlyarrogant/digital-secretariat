from datetime import UTC, datetime, timedelta

from src.secretariat.overview import _overview_from_row


def test_overview_projection_maps_counts_and_freshness() -> None:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    inbound_at = now - timedelta(minutes=15)
    send_at = now - timedelta(minutes=30)
    row = {
        "companies": 24,
        "registered_clients": 6,
        "inbound_received": 12,
        "inbound_unmatched": 3,
        "inbound_failed": 1,
        "cases_open": 14,
        "cases_overdue": 2,
        "cases_due_7d": 5,
        "cases_missing_controls": 1,
        "approvals_pending": 4,
        "approvals_overdue": 1,
        "approvals_failed": 2,
        "guests_active": 8,
        "guests_overdue": 1,
        "guests_incomplete": 1,
        "last_inbound_at": inbound_at,
        "last_send_attempt_at": send_at,
    }

    result = _overview_from_row(row, now, now - timedelta(hours=24))

    assert result.coverage.companies == 24
    assert result.inbound.unmatched == 3
    assert result.cases.due_within_7_days == 5
    assert result.approvals.failed == 2
    assert result.guests.incomplete == 1
    assert result.freshness.last_inbound_at == inbound_at
    assert result.freshness.last_send_attempt_at == send_at


def test_overview_projection_normalizes_null_counts() -> None:
    now = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    keys = (
        "companies",
        "registered_clients",
        "inbound_received",
        "inbound_unmatched",
        "inbound_failed",
        "cases_open",
        "cases_overdue",
        "cases_due_7d",
        "cases_missing_controls",
        "approvals_pending",
        "approvals_overdue",
        "approvals_failed",
        "guests_active",
        "guests_overdue",
        "guests_incomplete",
    )
    row = dict.fromkeys(keys)
    row.update(last_inbound_at=None, last_send_attempt_at=None)

    result = _overview_from_row(row, now, now - timedelta(hours=24))

    assert result.inbound.received == 0
    assert result.cases.open == 0
    assert result.approvals.pending == 0
    assert result.guests.active == 0
