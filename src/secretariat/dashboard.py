"""Detailed read-only queues used by the owner's operational dashboard."""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.secretariat.database import configure_read_only_session
from src.secretariat.outreach import read_outreach
from src.secretariat.overview import (
    OverviewRepository,
    PostgresOverviewRepository,
    _read_overview,
)
from src.secretariat.schemas import (
    ApprovalItem,
    AttentionItem,
    ClientItem,
    DeadlineItem,
    DeliveryVolumePoint,
    EvidenceRef,
    GuestItem,
    InboundItem,
    InvoiceAutomationSummary,
    MailVolumePoint,
    OperationalDashboard,
    OutboundDeliverySummary,
    PerformanceSummary,
    ResponseAutomationSummary,
    ResponseVolumePoint,
)


class DashboardRepository(OverviewRepository, Protocol):
    def read_dashboard(self, now: datetime) -> OperationalDashboard: ...


_DEADLINES_SQL = text(
    """
    SELECT o.id, o.company_id, COALESCE(c.short_name, c.name, c.nip) AS company_name,
           o.title, o.owner, o.due_date, o.state, o.category
    FROM client_obligations o
    JOIN companies c ON c.id = o.company_id
    WHERE o.status = 'open'
      AND o.due_date IS NOT NULL
      AND o.due_date <= :horizon
      AND COALESCE(o.state, 'pending') NOT IN ('filed', 'paid')
    ORDER BY o.due_date, o.company_id, o.id
    LIMIT 50
    """
)

_APPROVALS_SQL = text(
    """
    SELECT d.id, COALESCE(c.short_name, c.name, c.nip) AS company_name,
           d.to_address, d.subject, d.status, d.due_at, d.created_at,
           d.body AS body_text, jsonb_array_length(d.revisions) AS revision_count,
           d.error
    FROM email_drafts d
    LEFT JOIN companies c ON c.id = d.company_id
    WHERE d.status IN ('pending_approval', 'pending', 'waiting', 'failed')
    ORDER BY (d.status = 'failed') DESC, d.due_at ASC NULLS LAST, d.created_at DESC
    LIMIT 30
    """
)

_INBOUND_SQL = text(
    """
    SELECT r.id::text AS id, COALESCE(c.short_name, c.name, c.nip) AS company_name,
           r.sender_email, COALESCE(r.subject, '(bez tematu)') AS subject,
           r.processing_status, COALESCE(r.received_at, r.created_at) AS received_at,
           r.response_sent
    FROM email_processing_registry r
    LEFT JOIN companies c ON c.id = r.company_id
    ORDER BY COALESCE(r.received_at, r.created_at) DESC, r.id
    LIMIT 30
    """
)

_GUESTS_SQL = text(
    """
    SELECT id, COALESCE(display_name, email) AS display_name, email, stage,
           next_action, next_action_owner, next_action_due, last_event
    FROM guest_register
    WHERE stage NOT IN ('klient', 'odpadl')
    ORDER BY (next_action IS NULL OR next_action_owner IS NULL OR next_action_due IS NULL) DESC,
             next_action_due ASC NULLS FIRST, first_touch_at DESC
    LIMIT 30
    """
)

_CLIENTS_SQL = text(
    """
    SELECT v.company_id, COALESCE(c.short_name, c.name, c.nip) AS company_name,
           COALESCE(v.effective_status, 'unknown') AS effective_status,
           v.owner, COALESCE(v.service_scope, '{}'::jsonb) AS service_scope,
           COALESCE(v.contract_ok, false) AS contract_ok,
           v.vat_whitelist_status AS vat_status, COALESCE(v.ksef_token_present, false) AS ksef_token_present,
           COALESCE(v.mismatch_vat, false) AS mismatch_vat,
           COALESCE(v.mismatch_status, false) AS mismatch_status
    FROM client_registry_v v
    JOIN companies c ON c.id = v.company_id
    ORDER BY (COALESCE(v.mismatch_vat, false) OR COALESCE(v.mismatch_status, false)) DESC,
             company_name
    LIMIT 100
    """
)

_PERFORMANCE_SQL = text(
    """
    WITH inbound AS (
        SELECT processing_status, email_type
        FROM email_processing_registry
        WHERE COALESCE(received_at, created_at) >= :window_start
    ),
    linked_responses AS (
        SELECT sends.id, sends.automation_mode
        FROM email_send_log sends
        WHERE sends.success = true
          AND sends.sent_at >= :window_start
          AND sends.in_reply_to IS NOT NULL
    )
    SELECT
        COUNT(*) AS inbound_total,
        COUNT(*) FILTER (WHERE email_type = 'ocr_extraction') AS invoice_received,
        COUNT(*) FILTER (
            WHERE email_type = 'ocr_extraction' AND processing_status = 'processed'
        ) AS invoice_processed,
        COUNT(*) FILTER (
            WHERE email_type = 'ocr_extraction' AND processing_status = 'failed'
        ) AS invoice_failed,
        (SELECT COUNT(*) FROM linked_responses) AS responses_sent,
        (SELECT COUNT(*) FROM linked_responses
          WHERE automation_mode = 'formatted_approved') AS formatted_responses,
        (SELECT COUNT(*) FROM linked_responses
          WHERE automation_mode IN ('automatic_template', 'automatic_ai')) AS automatic_responses,
        (SELECT COUNT(*) FROM linked_responses
          WHERE automation_mode IS NULL) AS unclassified_responses,
        (SELECT COUNT(*) FROM email_send_log
          WHERE success = true AND sent_at >= :window_start) AS outbound_accepted,
        (SELECT COUNT(*) FROM email_send_log
          WHERE success = false AND sent_at >= :window_start) AS outbound_failed,
        (SELECT COUNT(*) FROM email_send_log
          WHERE sent_at >= :window_start
            AND COALESCE(error_message, '') ILIKE '%%bounce%%') AS outbound_bounced
    FROM inbound
    """
)

_DAILY_MAIL_SQL = text(
    """
    SELECT (COALESCE(received_at, created_at) AT TIME ZONE 'Europe/Warsaw')::date AS day,
           COUNT(*) AS inbound,
           COUNT(*) FILTER (WHERE email_type = 'ocr_extraction') AS invoice_channel,
           COUNT(*) FILTER (
               WHERE email_type = 'ocr_extraction' AND processing_status = 'processed'
           ) AS processed,
           COUNT(*) FILTER (
               WHERE email_type = 'ocr_extraction' AND processing_status = 'failed'
           ) AS failed
    FROM email_processing_registry
    WHERE COALESCE(received_at, created_at) >= :window_start
    GROUP BY 1
    ORDER BY 1
    """
)

_DAILY_SENDS_SQL = text(
    """
    SELECT (sent_at AT TIME ZONE 'Europe/Warsaw')::date AS day,
           COUNT(*) FILTER (WHERE success = true) AS accepted,
           COUNT(*) FILTER (WHERE success = false) AS failed,
           COUNT(*) FILTER (
               WHERE success = true AND in_reply_to IS NOT NULL
           ) AS linked,
           COUNT(*) FILTER (
               WHERE success = true AND in_reply_to IS NOT NULL
                 AND automation_mode = 'formatted_approved'
           ) AS formatted_approved,
           COUNT(*) FILTER (
               WHERE success = true AND in_reply_to IS NOT NULL
                 AND automation_mode IN ('automatic_template', 'automatic_ai')
           ) AS automatic,
           COUNT(*) FILTER (
               WHERE success = true AND in_reply_to IS NOT NULL
                 AND automation_mode IS NULL
           ) AS unclassified
    FROM email_send_log
    WHERE sent_at >= :window_start
    GROUP BY 1
    ORDER BY 1
    """
)

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "neutral": 2}
_KIND_ORDER = {"decision": 0, "deadline": 1, "inbound": 2, "relationship": 3}
_NO_AUTOMATIC_ACTION = "Brak automatycznej akcji; sprawa pozostaje w kolejce."
_WARSAW = ZoneInfo("Europe/Warsaw")


def _days_label(value: int) -> str:
    return "1 dzień" if value == 1 else f"{value} dni"


def _attention_timestamp(item: AttentionItem, now: datetime) -> float:
    if item.due_at is not None:
        due_at = item.due_at
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=now.tzinfo)
        return due_at.timestamp()
    if item.due_on is not None:
        return datetime.combine(item.due_on, time.min, tzinfo=now.tzinfo).timestamp()
    return float("inf")


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator * 100 / denominator, 2)


def _calendar_days(last_day: date, count: int) -> list[date]:
    first_day = last_day - timedelta(days=count - 1)
    return [first_day + timedelta(days=offset) for offset in range(count)]


def build_attention_items(
    *,
    now: datetime,
    approvals: list[ApprovalItem],
    deadlines: list[DeadlineItem],
    inbound: list[InboundItem],
    guests: list[GuestItem],
) -> list[AttentionItem]:
    """Build an explicit, deterministic owner-attention queue from source facts."""

    items: list[AttentionItem] = []
    local_today = now.astimezone(_WARSAW).date()

    for approval in approvals:
        overdue = bool(approval.due_at and approval.due_at < now)
        failed = approval.status == "failed"
        if failed:
            why_now = "Próba przygotowania lub wysłania wiadomości zakończyła się błędem."
            recommendation = "Sprawdź przyczynę błędu przed ponowieniem wysyłki."
        elif overdue:
            why_now = "Minął termin decyzji dla tej wiadomości."
            recommendation = "Sprawdź treść i zdecyduj, czy wiadomość zatwierdzić albo odrzucić."
        else:
            why_now = "Wiadomość czeka na decyzję właściciela przed wysłaniem."
            recommendation = "Sprawdź treść i zdecyduj, czy wiadomość zatwierdzić albo odrzucić."
        items.append(
            AttentionItem(
                id=f"decision:{approval.id}",
                kind="decision",
                severity="critical" if failed or overdue else "warning",
                title=approval.subject,
                company_name=approval.company_name,
                why_now=why_now,
                recommendation=recommendation,
                default_action=_NO_AUTOMATIC_ACTION,
                owner="właściciel",
                due_at=approval.due_at,
                evidence=EvidenceRef(
                    source_type="email_draft",
                    source_id=str(approval.id),
                    label=f"Szkic wiadomości #{approval.id}",
                ),
            )
        )

    for deadline in deadlines:
        days = (deadline.due_date - local_today).days
        if days > 3:
            continue
        severity: Literal["critical", "warning", "neutral"]
        if days < 0:
            severity = "critical"
            why_now = f"Termin minął {_days_label(abs(days))} temu."
            recommendation = "Potwierdź stan realizacji i przypisz działanie naprawcze."
        elif days == 0:
            severity = "critical"
            why_now = "Termin przypada dziś."
            recommendation = "Potwierdź właściciela i gotowość do realizacji."
        else:
            severity = "warning"
            why_now = f"Termin przypada za {_days_label(days)}."
            recommendation = "Potwierdź właściciela i gotowość do realizacji."
        items.append(
            AttentionItem(
                id=f"deadline:{deadline.id}",
                kind="deadline",
                severity=severity,
                title=deadline.title,
                company_name=deadline.company_name,
                why_now=why_now,
                recommendation=recommendation,
                default_action=_NO_AUTOMATIC_ACTION,
                owner=deadline.owner,
                due_on=deadline.due_date,
                evidence=EvidenceRef(
                    source_type="obligation",
                    source_id=str(deadline.id),
                    label=f"Obowiązek #{deadline.id}",
                ),
            )
        )

    for message in inbound:
        received_at = message.received_at
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=now.tzinfo)
        if received_at < now - timedelta(hours=24):
            continue
        failed = message.processing_status == "failed"
        unmatched = message.company_name is None
        if not failed and not unmatched:
            continue
        items.append(
            AttentionItem(
                id=f"inbound:{message.id}",
                kind="inbound",
                severity="critical" if failed else "warning",
                title=message.subject,
                company_name=message.company_name,
                why_now=(
                    "Przetwarzanie wiadomości zakończyło się błędem."
                    if failed
                    else "Wiadomość nie jest przypisana do firmy ani relacji."
                ),
                recommendation=(
                    "Sprawdź błąd przetwarzania i zabezpiecz ręczną obsługę wiadomości."
                    if failed
                    else "Przypisz wiadomość do firmy albo oznacz ją jako nową relację."
                ),
                default_action=_NO_AUTOMATIC_ACTION,
                owner="sekretariat",
                due_at=received_at + timedelta(hours=24),
                evidence=EvidenceRef(
                    source_type="inbound_email",
                    source_id=message.id,
                    label=f"Wpływ email {message.id}",
                ),
            )
        )

    for guest in guests:
        incomplete = (
            not guest.next_action or not guest.next_action_owner or not guest.next_action_due
        )
        overdue = bool(guest.next_action_due and guest.next_action_due < local_today)
        if not incomplete and not overdue:
            continue
        items.append(
            AttentionItem(
                id=f"relationship:{guest.id}",
                kind="relationship",
                severity="warning",
                title=guest.next_action or f"Uzupełnij kolejny krok dla {guest.display_name}",
                company_name=guest.display_name,
                why_now=(
                    "Relacja nie ma kompletnego kolejnego kroku, właściciela i terminu."
                    if incomplete
                    else "Termin kolejnego kroku w relacji już minął."
                ),
                recommendation=(
                    "Uzupełnij kolejny krok, osobę odpowiedzialną i termin."
                    if incomplete
                    else "Zaktualizuj kolejny krok albo zamknij relację."
                ),
                default_action=_NO_AUTOMATIC_ACTION,
                owner=guest.next_action_owner or "sekretariat",
                due_on=guest.next_action_due,
                evidence=EvidenceRef(
                    source_type="guest_register",
                    source_id=str(guest.id),
                    label=f"Rejestr relacji #{guest.id}",
                ),
            )
        )

    return sorted(
        items,
        key=lambda item: (
            # Decyzje właściciela (szkice do zatwierdzenia) ZAWSZE na szczycie
            # kolejki — strona "Dzisiaj" tnie listę (limit), a bez tego draft
            # o statusie warning spadał poza widoczne pozycje i był niewidoczny
            # (product rule). Kolejka decyzji > reszta uwagi.
            0 if item.kind == "decision" else 1,
            _SEVERITY_ORDER[item.severity],
            _attention_timestamp(item, now),
            _KIND_ORDER[item.kind],
            item.id,
        ),
    )


class PostgresDashboardRepository(PostgresOverviewRepository):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        super().__init__(session_factory)
        self._session_factory = session_factory

    def read_dashboard(self, now: datetime) -> OperationalDashboard:
        session = self._session_factory()
        try:
            configure_read_only_session(session)
            overview = _read_overview(session, now)
            local_today = now.astimezone(_WARSAW).date()
            calendar_days = _calendar_days(local_today, 30)
            window_start = datetime.combine(calendar_days[0], time.min, tzinfo=_WARSAW)
            deadline_rows = session.execute(
                _DEADLINES_SQL,
                {"horizon": now.astimezone(_WARSAW).date() + timedelta(days=14)},
            ).mappings()
            approval_rows = session.execute(_APPROVALS_SQL).mappings()
            inbound_rows = session.execute(_INBOUND_SQL).mappings()
            guest_rows = session.execute(_GUESTS_SQL).mappings()
            client_rows = session.execute(_CLIENTS_SQL).mappings()
            performance_row = (
                session.execute(
                    _PERFORMANCE_SQL,
                    {"window_start": window_start},
                )
                .mappings()
                .one()
            )
            daily_mail_rows = session.execute(
                _DAILY_MAIL_SQL,
                {"window_start": window_start},
            ).mappings()
            daily_send_rows = session.execute(
                _DAILY_SENDS_SQL,
                {"window_start": window_start},
            ).mappings()
            deadlines = [DeadlineItem.model_validate(row) for row in deadline_rows]
            approvals = [ApprovalItem.model_validate(row) for row in approval_rows]
            inbound = [InboundItem.model_validate(row) for row in inbound_rows]
            guests = [GuestItem.model_validate(row) for row in guest_rows]
            invoice_received = int(performance_row["invoice_received"] or 0)
            invoice_processed = int(performance_row["invoice_processed"] or 0)
            inbound_total = int(performance_row["inbound_total"] or 0)
            responses_sent = int(performance_row["responses_sent"] or 0)
            formatted_responses = int(performance_row["formatted_responses"] or 0)
            automatic_responses = int(performance_row["automatic_responses"] or 0)
            daily_mail: dict[date, dict[str, Any]] = {
                row["day"]: dict(row) for row in daily_mail_rows
            }
            daily_sends: dict[date, dict[str, Any]] = {
                row["day"]: dict(row) for row in daily_send_rows
            }
            return OperationalDashboard(
                overview=overview,
                attention=build_attention_items(
                    now=now,
                    approvals=approvals,
                    deadlines=deadlines,
                    inbound=inbound,
                    guests=guests,
                ),
                deadlines=deadlines,
                approvals=approvals,
                inbound=inbound,
                guests=guests,
                clients=[ClientItem.model_validate(row) for row in client_rows],
                performance=PerformanceSummary(
                    invoices=InvoiceAutomationSummary(
                        inbound_total=inbound_total,
                        received=invoice_received,
                        processed=invoice_processed,
                        failed=int(performance_row["invoice_failed"] or 0),
                        share_of_inbound=_percentage(invoice_received, inbound_total),
                        processing_rate=_percentage(invoice_processed, invoice_received),
                        touchless_rate=None,
                        daily=[
                            MailVolumePoint(
                                day=day,
                                inbound=int(daily_mail.get(day, {}).get("inbound", 0) or 0),
                                invoice_channel=int(
                                    daily_mail.get(day, {}).get("invoice_channel", 0) or 0
                                ),
                                processed=int(daily_mail.get(day, {}).get("processed", 0) or 0),
                                failed=int(daily_mail.get(day, {}).get("failed", 0) or 0),
                            )
                            for day in calendar_days
                        ],
                    ),
                    responses=ResponseAutomationSummary(
                        sent=responses_sent,
                        formatted_approved=formatted_responses,
                        automatic=automatic_responses,
                        unclassified_origin=int(performance_row["unclassified_responses"] or 0),
                        classification_coverage=_percentage(
                            formatted_responses + automatic_responses,
                            responses_sent,
                        ),
                        daily=[
                            ResponseVolumePoint(
                                day=day,
                                linked=int(daily_sends.get(day, {}).get("linked", 0) or 0),
                                formatted_approved=int(
                                    daily_sends.get(day, {}).get("formatted_approved", 0) or 0
                                ),
                                automatic=int(daily_sends.get(day, {}).get("automatic", 0) or 0),
                                unclassified=int(
                                    daily_sends.get(day, {}).get("unclassified", 0) or 0
                                ),
                            )
                            for day in calendar_days
                        ],
                    ),
                    delivery=OutboundDeliverySummary(
                        accepted=int(performance_row["outbound_accepted"] or 0),
                        failed=int(performance_row["outbound_failed"] or 0),
                        bounced=int(performance_row["outbound_bounced"] or 0),
                        daily=[
                            DeliveryVolumePoint(
                                day=day,
                                accepted=int(daily_sends.get(day, {}).get("accepted", 0) or 0),
                                failed=int(daily_sends.get(day, {}).get("failed", 0) or 0),
                            )
                            for day in calendar_days
                        ],
                    ),
                    outreach=read_outreach(),
                ),
            )
        finally:
            session.rollback()
            session.close()
