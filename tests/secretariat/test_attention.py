from datetime import UTC, datetime, timedelta

from src.secretariat.dashboard import build_attention_items
from src.secretariat.schemas import ApprovalItem, DeadlineItem, GuestItem, InboundItem


def test_attention_projection_prioritizes_critical_facts() -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)
    items = build_attention_items(
        now=now,
        approvals=[
            ApprovalItem(
                id=7,
                company_name="Reset Media",
                to_address="client@example.com",
                subject="Akceptacja odpowiedzi",
                status="pending_approval",
                due_at=now + timedelta(hours=2),
                created_at=now - timedelta(minutes=10),
            )
        ],
        deadlines=[
            DeadlineItem(
                id=10,
                company_id=84,
                company_name="Instytut",
                title="Złożyć JPK",
                owner="us",
                due_date=now.date() - timedelta(days=1),
                state="pending",
                category="jpk_vat",
            )
        ],
        inbound=[],
        guests=[],
    )

    assert [item.kind for item in items] == ["decision", "deadline"]
    assert items[0].default_action.startswith("Brak automatycznej akcji")
    assert items[1].severity == "critical"
    assert items[1].why_now == "Termin minął 1 dzień temu."
    assert items[1].evidence.source_type == "obligation"


def test_attention_projection_only_promotes_exceptional_inbound_and_relationships() -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)
    items = build_attention_items(
        now=now,
        approvals=[],
        deadlines=[],
        inbound=[
            InboundItem(
                id="matched",
                company_name="Klient",
                sender_email="client@example.com",
                subject="Dokumenty",
                processing_status="processed",
                received_at=now,
            ),
            InboundItem(
                id="unmatched",
                company_name=None,
                sender_email="new@example.com",
                subject="Zapytanie",
                processing_status="processed",
                received_at=now - timedelta(minutes=5),
            ),
            InboundItem(
                id="historical-unmatched",
                company_name=None,
                sender_email="old@example.com",
                subject="Stare zapytanie",
                processing_status="processed",
                received_at=now - timedelta(days=2),
            ),
        ],
        guests=[
            GuestItem(
                id=3,
                display_name="Nowa relacja",
                email="guest@example.com",
                stage="nowy",
                next_action=None,
                next_action_owner=None,
                next_action_due=None,
                last_event="Pierwszy mail",
            ),
            GuestItem(
                id=4,
                display_name="Kompletna relacja",
                email="complete@example.com",
                stage="rozmowa",
                next_action="Oddzwonić",
                next_action_owner="sekretariat",
                next_action_due=now.date() + timedelta(days=2),
                last_event="Rozmowa",
            ),
        ],
    )

    assert {item.id for item in items} == {"inbound:unmatched", "relationship:3"}
    assert all(item.severity == "warning" for item in items)


def test_attention_projection_keeps_later_deadlines_out_of_owner_focus() -> None:
    now = datetime(2026, 7, 19, 9, 0, tzinfo=UTC)
    items = build_attention_items(
        now=now,
        approvals=[],
        deadlines=[
            DeadlineItem(
                id=20,
                company_id=84,
                company_name="Instytut",
                title="Złożyć JPK",
                owner="us",
                due_date=now.date() + timedelta(days=8),
                state="pending",
                category="jpk_vat",
            )
        ],
        inbound=[],
        guests=[],
    )

    assert items == []
