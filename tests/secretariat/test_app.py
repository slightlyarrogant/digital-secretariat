import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.secretariat.actions import (
    DraftActionConflict,
    ReplyActionError,
    ReplyActionResult,
)
from src.secretariat.app import create_app
from src.secretariat.dashboard import build_attention_items
from src.secretariat.schemas import (
    ApprovalItem,
    ApprovalSummary,
    CaseSummary,
    ClientItem,
    CoverageSummary,
    DeadlineItem,
    DeliveryVolumePoint,
    FreshnessSummary,
    GuestItem,
    GuestSummary,
    InboundItem,
    InboundSummary,
    InvoiceAutomationSummary,
    MailVolumePoint,
    MessageAttachment,
    MessageContent,
    OperationalDashboard,
    OperationalOverview,
    OutboundDeliverySummary,
    OutreachSummary,
    PerformanceSummary,
    ResponseAutomationSummary,
    ResponseVolumePoint,
)
from src.secretariat.web import _client_rows


class StubRepository:
    def __init__(self) -> None:
        self.missing: list[str] = []
        self.fail = False
        self.dashboard_subject = "Prośba o akceptację"
        self.include_approval = True
        self.approval_status = "pending_approval"
        self.approval_error: str | None = None
        self.response_sent = False

    def missing_relations(self) -> list[str]:
        if self.fail:
            raise OperationalError("SELECT 1", {}, Exception("database down"))
        return self.missing

    def read(self, now: datetime) -> OperationalOverview:
        if self.fail:
            raise OperationalError("SELECT overview", {}, Exception("database down"))
        return OperationalOverview(
            generated_at=now,
            window_started_at=now - timedelta(hours=24),
            coverage=CoverageSummary(companies=24, registered_clients=6),
            inbound=InboundSummary(received=12, unmatched=3, failed=1),
            cases=CaseSummary(open=14, overdue=2, due_within_7_days=5, missing_controls=1),
            approvals=ApprovalSummary(
                pending=int(self.include_approval and self.approval_status == "pending_approval"),
                overdue=0,
                failed=int(self.include_approval and self.approval_status == "failed"),
            ),
            guests=GuestSummary(active=8, overdue=1, incomplete=1),
            freshness=FreshnessSummary(
                last_inbound_at=now - timedelta(minutes=15),
                last_send_attempt_at=now - timedelta(minutes=30),
            ),
        )

    def read_dashboard(self, now: datetime) -> OperationalDashboard:
        if self.fail:
            raise OperationalError("SELECT dashboard", {}, Exception("database down"))
        deadlines = [
            DeadlineItem(
                id=10,
                company_id=84,
                company_name="Instytut",
                title="Złożyć JPK",
                owner="us",
                due_date=now.date() + timedelta(days=2),
                state="prepared",
                category="jpk_vat",
            )
        ]
        approvals = (
            [
                ApprovalItem(
                    id=7,
                    company_name="Instytut",
                    to_address="client@example.com",
                    subject=self.dashboard_subject,
                    status=self.approval_status,
                    due_at=now + timedelta(hours=2),
                    created_at=now - timedelta(minutes=10),
                    body_text=(
                        "Dzień dobry. Potwierdzamy otrzymanie dokumentów. "
                        "Wrócimy z odpowiedzią po ich sprawdzeniu."
                    ),
                    revision_count=1,
                    error=self.approval_error,
                )
            ]
            if self.include_approval
            else []
        )
        inbound = [
            InboundItem(
                id="00000000-0000-0000-0000-000000000001",
                company_name=None,
                sender_email="guest@example.com",
                subject="Nowe zapytanie",
                processing_status="processed",
                received_at=now - timedelta(minutes=5),
                response_sent=self.response_sent,
            )
        ]
        guests = [
            GuestItem(
                id=3,
                display_name="Jan Testowy",
                email="guest@example.com",
                stage="nowy",
                next_action="Oddzwonić",
                next_action_owner="sekretariat",
                next_action_due=now.date() + timedelta(days=1),
                last_event="Pierwszy mail",
            )
        ]
        return OperationalDashboard(
            overview=self.read(now),
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
            clients=[
                ClientItem(
                    company_id=84,
                    company_name="Instytut",
                    effective_status="active",
                    owner="bogdan",
                    service_scope={"jpk_vat": True},
                    contract_ok=True,
                    vat_status="active",
                    ksef_token_present=True,
                    mismatch_vat=False,
                    mismatch_status=False,
                )
            ],
            performance=PerformanceSummary(
                invoices=InvoiceAutomationSummary(
                    inbound_total=12,
                    received=8,
                    processed=7,
                    failed=1,
                    share_of_inbound=66.67,
                    processing_rate=87.5,
                    touchless_rate=None,
                    daily=[
                        MailVolumePoint(
                            day=now.date(), inbound=12, invoice_channel=8, processed=7, failed=1
                        )
                    ],
                ),
                responses=ResponseAutomationSummary(
                    sent=3,
                    formatted_approved=2,
                    automatic=None,
                    unclassified_origin=1,
                    classification_coverage=66.67,
                    daily=[
                        ResponseVolumePoint(
                            day=now.date(),
                            linked=3,
                            formatted_approved=2,
                            automatic=0,
                            unclassified=1,
                        )
                    ],
                ),
                delivery=OutboundDeliverySummary(
                    accepted=12,
                    failed=1,
                    bounced=0,
                    daily=[DeliveryVolumePoint(day=now.date(), accepted=12, failed=1)],
                ),
                outreach=OutreachSummary(
                    available=False,
                    sent=0,
                    replied=0,
                    human_replies=0,
                    registrations=0,
                    converted=0,
                    unsubscribed=0,
                    failed=0,
                    reply_rate=None,
                    conversion_rate=None,
                    variants=[],
                ),
            ),
        )


@pytest.fixture
def repository() -> StubRepository:
    return StubRepository()


@pytest.fixture
def client(repository: StubRepository, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    monkeypatch.delenv("SECRETARIAT_SNAPSHOT_FILE", raising=False)
    return TestClient(create_app(repository))


def _identity_headers() -> dict[str, str]:
    return {"Tailscale-User-Login": "owner@example.com"}


def test_liveness_contains_no_business_data(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "digital-secretariat",
        "version": "0.1.0",
    }


def test_readiness_reports_missing_relations(
    client: TestClient, repository: StubRepository
) -> None:
    repository.missing = ["guest_register"]

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "digital-secretariat",
    }
    assert "guest_register" not in response.text


def test_overview_requires_identity(client: TestClient) -> None:
    response = client.get("/api/v1/overview")

    assert response.status_code == 401


def test_overview_returns_read_only_projection(client: TestClient) -> None:
    response = client.get("/api/v1/overview", headers=_identity_headers())

    assert response.status_code == 200
    assert response.json()["coverage"] == {"companies": 24, "registered_clients": 6}
    assert response.json()["inbound"]["unmatched"] == 3
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    )


def test_overview_hides_database_error(client: TestClient, repository: StubRepository) -> None:
    repository.fail = True

    response = client.get("/api/v1/overview", headers=_identity_headers())

    assert response.status_code == 503
    assert response.json() == {"detail": "Operational projection is unavailable"}
    assert "database down" not in response.text


def test_control_plane_exposes_no_write_method(client: TestClient) -> None:
    response = client.post("/api/v1/overview", headers=_identity_headers())

    assert response.status_code == 405


def test_dashboard_api_returns_operational_lists(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard", headers=_identity_headers())

    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.4"
    assert response.json()["attention"][0]["why_now"]
    assert response.json()["deadlines"][0]["company_name"] == "Instytut"
    assert response.json()["approvals"][0]["status"] == "pending_approval"
    assert response.json()["inbound"][0]["company_name"] is None
    assert response.json()["clients"][0]["contract_ok"] is True


def test_dashboard_page_requires_identity(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 401


def test_today_page_surfaces_decision_queue_with_write_controls(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    action_client = TestClient(create_app(repository, draft_actions=StubDraftActions()))

    response = action_client.get("/", headers=_identity_headers())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for label in (
        "Dzisiaj",
        "3 sprawy wymagają uwagi, bez alarmów krytycznych.",
        "Do decyzji",
        "Wymaga uwagi",
        "Najbliższe terminy",
        "Puls dnia",
        "Zatwierdź i wyślij",
        "Odrzuć",
        "Edytuj szkic",
    ):
        assert label in response.text
    assert response.text.index("Do decyzji") < response.text.index("Wymaga uwagi")
    assert 'id="draft-7"' in response.text
    assert 'href="#draft-7"' in response.text
    assert response.text.count('method="post"') == 3
    assert response.text.count('href="/system"') >= 2


def test_navigation_uses_pending_approval_count_on_every_view(client: TestClient) -> None:
    for path in ("/", "/inbox", "/cases", "/performance"):
        response = client.get(path, headers=_identity_headers())

        assert response.status_code == 200
        assert (
            '<a href="/inbox"><span>Skrzynka</span><span class="nav-count">1</span></a>'
            in response.text
            or '<a href="/inbox" aria-current="page"><span>Skrzynka</span>'
            '<span class="nav-count">1</span></a>' in response.text
        )


def test_today_page_has_quiet_empty_decision_state(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository.include_approval = False
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    action_client = TestClient(create_app(repository, draft_actions=StubDraftActions()))

    response = action_client.get("/", headers=_identity_headers())

    assert response.status_code == 200
    assert "Brak wiadomości oczekujących na decyzję." in response.text
    assert 'id="draft-' not in response.text
    assert 'method="post"' not in response.text


def test_failed_draft_shows_registered_error(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository.approval_status = "failed"
    repository.approval_error = "SMTP 550: mailbox unavailable"
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    action_client = TestClient(create_app(repository, draft_actions=StubDraftActions()))

    response = action_client.get("/", headers=_identity_headers())

    assert response.status_code == 200
    assert 'class="mail-item critical" id="draft-7"' in response.text
    assert "Błąd ostatniej próby" in response.text
    assert "SMTP 550: mailbox unavailable" in response.text
    assert "Ponów wysyłkę" in response.text


@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/inbox", "Skrzynka"),
        ("/cases", "Sprawy"),
        ("/relationships", "Relacje"),
        ("/calendar", "Kalendarz"),
        ("/performance", "Wyniki"),
        ("/system", "System"),
    ],
)
def test_workspace_views_are_separate_pages(client: TestClient, path: str, heading: str) -> None:
    response = client.get(path, headers=_identity_headers())

    assert response.status_code == 200
    assert f"<h1>{heading}</h1>" in response.text
    assert f'href="{path}" aria-current="page"' in response.text


def test_ui_translates_domain_codes(client: TestClient) -> None:
    cases = client.get("/cases", headers=_identity_headers())
    relationships = client.get("/relationships", headers=_identity_headers())

    assert "jpk_vat" not in cases.text
    assert "JPK_V7M" in cases.text
    assert ">us<" not in cases.text
    assert "Sekretariat" in cases.text
    assert "Braki w kotwicach" not in relationships.text


def test_client_anchor_badges_use_registry_contract_and_vat_mismatch() -> None:
    common = {
        "effective_status": "active",
        "owner": "bogdan",
        "service_scope": {},
        "vat_status": "active",
        "ksef_token_present": True,
        "mismatch_status": False,
    }
    rendered = _client_rows(
        [
            ClientItem(
                company_id=30,
                company_name="AutoOffice",
                contract_ok=True,
                mismatch_vat=False,
                **common,
            ),
            ClientItem(
                company_id=68,
                company_name="KDŁUGA",
                contract_ok=False,
                mismatch_vat=False,
                **common,
            ),
            ClientItem(
                company_id=69,
                company_name="VERO",
                contract_ok=False,
                mismatch_vat=True,
                **common,
            ),
        ]
    )

    autooffice, kdluga, vero = rendered.split('class="record-row client-row"')[1:]
    assert 'anchor ok">Umowa' in autooffice
    assert 'anchor ok">VAT' in autooffice
    assert 'anchor missing">Umowa' in kdluga
    assert 'anchor ok">VAT' in kdluga
    assert 'anchor missing">Umowa' in vero
    assert 'anchor missing">VAT' in vero


def test_performance_page_separates_measured_results_from_unknown_automation(
    client: TestClient,
) -> None:
    response = client.get("/performance", headers=_identity_headers())

    assert response.status_code == 200
    assert "Ruch w sekretariacie" in response.text
    assert "Kanał faktury@" in response.text
    assert "66.67%" in response.text
    assert "Pochodzenie" in response.text
    assert "Warianty kampanii" in response.text
    assert response.text.count('class="line-chart"') >= 2
    assert 'class="donut"' in response.text
    assert "Zatwierdzone" in response.text
    assert "Niemierzone" in response.text
    assert "Liczymy wyłącznie wysyłki powiązane" in response.text


def test_message_preview_renders_sanitized_content_and_attachment_metadata(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    content = MessageContent(
        registry_id="00000000-0000-0000-0000-000000000001",
        available=True,
        mailbox="faktury@example.com",
        from_address="client@example.com",
        to_address="faktury@example.com",
        subject='<script>alert("x")</script>',
        body_text='<img src=x onerror=alert("x")> Treść',
        attachments=[
            MessageAttachment(
                filename="FV-06.pdf",
                content_type="application/pdf",
                size_bytes=1024,
            )
        ],
    )
    preview_client = TestClient(create_app(repository, message_reader=lambda _id: content))

    response = preview_client.get(
        "/inbox/00000000-0000-0000-0000-000000000001",
        headers=_identity_headers(),
    )

    assert response.status_code == 200
    assert "FV-06.pdf" in response.text
    assert "faktury@example.com" in response.text
    assert "<script>" not in response.text
    assert "&lt;img src=x" in response.text
    assert "Zatwierdź" not in response.text


def test_inbox_reads_messages_inline_without_page_navigation(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    calls: list[str] = []

    def reader(message_id: str) -> MessageContent:
        calls.append(message_id)
        return MessageContent(
            registry_id=message_id,
            available=True,
            mailbox="faktury@example.com",
            from_address="Client <client@example.com>",
            subject="Faktura za czerwiec",
            body_text=(
                "Dzień dobry. Przesyłam fakturę za czerwiec. "
                "Termin płatności to 25 lipca. <script>nie wykonuj</script> "
                "To zdanie pozostaje dostępne w pełnym podglądzie."
            ),
            attachments=[
                MessageAttachment(
                    filename="FV-06.pdf",
                    content_type="application/pdf",
                    size_bytes=2048,
                )
            ],
        )

    inbox_client = TestClient(create_app(repository, message_reader=reader))

    response = inbox_client.get("/inbox", headers=_identity_headers())

    assert response.status_code == 200
    assert calls == [registry_id]
    assert response.text.count('class="mail-item') == 2
    assert 'class="mail-snippet"' in response.text
    assert "Przesyłam fakturę za czerwiec" in response.text
    assert "To zdanie pozostaje dostępne w pełnym podglądzie" in response.text
    assert "FV-06.pdf" in response.text
    assert "<script>" not in response.text
    assert "&lt;script&gt;nie wykonuj&lt;/script&gt;" in response.text
    assert f'href="/inbox/{registry_id}"' not in response.text
    assert 'target="_blank"' not in response.text


class StubReplyActions:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, dict[str, object]]] = []
        self.create_error: ReplyActionError | None = None
        self.release_status = "sent"

    def create(self, registry_id: str, **values: object) -> ReplyActionResult:
        if self.create_error is not None:
            raise self.create_error
        self.calls.append(("create", registry_id, values))
        return ReplyActionResult(draft_id=25, status="pending_approval")

    def release(self, draft_id: int, **values: object) -> ReplyActionResult:
        self.calls.append(("release", draft_id, values))
        return ReplyActionResult(draft_id=draft_id, status=self.release_status)


def _reply_content(registry_id: str) -> MessageContent:
    return MessageContent(
        registry_id=registry_id,
        available=True,
        mailbox="faktury@example.com",
        from_address="guest@example.com",
        to_address="faktury@example.com",
        sent_at="2026-07-21T16:00:00+02:00",
        subject="Nowe zapytanie",
        body_text="Dzień dobry, chciałbym rozpocząć współpracę.",
    )


def _reply_token(page: str, registry_id: str) -> str:
    match = re.search(
        rf'action="/inbox/{registry_id}/reply".*?name="action_token" value="([a-f0-9]{{64}})"',
        page,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_inbox_renders_inline_reply_composer_when_enabled(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    actions = StubReplyActions()
    reply_client = TestClient(
        create_app(
            repository,
            message_reader=_reply_content,
            reply_actions=actions,
        )
    )

    response = reply_client.get("/inbox", headers=_identity_headers())

    assert response.status_code == 200
    assert 'aria-label="Krótka odpowiedź"' in response.text
    assert 'value="Re: Nowe zapytanie"' in response.text
    assert "Zapisz szkic" in response.text
    assert "Zatwierdź i wyślij" in response.text
    assert 'name="to_address"' not in response.text
    assert 'name="from_address"' not in response.text
    assert _reply_token(response.text, registry_id)


@pytest.mark.parametrize(
    ("intent", "expected_notice", "expected_actions"),
    [
        ("queue", "reply_queued", ["create"]),
        ("send", "reply_sent", ["create", "release"]),
    ],
)
def test_inline_reply_uses_canonical_reply_and_release_actions(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
    intent: str,
    expected_notice: str,
    expected_actions: list[str],
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    actions = StubReplyActions()
    reply_client = TestClient(
        create_app(repository, message_reader=_reply_content, reply_actions=actions)
    )
    page = reply_client.get("/inbox", headers=_identity_headers()).text

    response = reply_client.post(
        f"/inbox/{registry_id}/reply",
        headers=_identity_headers(),
        data={
            "subject": "Re: Nowe zapytanie",
            "body": "Dziękuję. Proszę o numer telefonu.",
            "intent": intent,
            "action_token": _reply_token(page, registry_id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/inbox?notice={expected_notice}#draft-25"
    assert [call[0] for call in actions.calls] == expected_actions
    create_values = actions.calls[0][2]
    assert create_values == {
        "subject": "Re: Nowe zapytanie",
        "body": "Dziękuję. Proszę o numer telefonu.",
        "created_by": "secretariat-board:owner@example.com",
    }
    if intent == "send":
        assert actions.calls[1][2]["expected_revision"] == 0


def test_inline_reply_rejects_invalid_signed_token_before_rail(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    actions = StubReplyActions()
    reply_client = TestClient(
        create_app(repository, message_reader=_reply_content, reply_actions=actions)
    )

    response = reply_client.post(
        f"/inbox/{registry_id}/reply",
        headers=_identity_headers(),
        data={
            "subject": "Re: Nowe zapytanie",
            "body": "Treść",
            "intent": "send",
            "action_token": "0" * 64,
        },
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert actions.calls == []


def test_inline_reply_surfaces_unknown_source_mailbox_without_send(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    actions = StubReplyActions()
    actions.create_error = ReplyActionError("source_mailbox_unknown")
    reply_client = TestClient(
        create_app(repository, message_reader=_reply_content, reply_actions=actions)
    )
    page = reply_client.get("/inbox", headers=_identity_headers()).text

    response = reply_client.post(
        f"/inbox/{registry_id}/reply",
        headers=_identity_headers(),
        data={
            "subject": "Re: Nowe zapytanie",
            "body": "Treść",
            "intent": "send",
            "action_token": _reply_token(page, registry_id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=reply_mailbox_unknown"
    assert actions.calls == []


def test_inline_reply_surfaces_freshness_block_and_keeps_draft(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    registry_id = "00000000-0000-0000-0000-000000000001"
    actions = StubReplyActions()
    actions.release_status = "blocked"
    reply_client = TestClient(
        create_app(repository, message_reader=_reply_content, reply_actions=actions)
    )
    page = reply_client.get("/inbox", headers=_identity_headers()).text

    response = reply_client.post(
        f"/inbox/{registry_id}/reply",
        headers=_identity_headers(),
        data={
            "subject": "Re: Nowe zapytanie",
            "body": "Treść",
            "intent": "send",
            "action_token": _reply_token(page, registry_id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=reply_blocked#draft-25"
    assert [call[0] for call in actions.calls] == ["create", "release"]


def test_inbox_hides_reply_composer_after_response_was_sent(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    repository.response_sent = True
    actions = StubReplyActions()
    reply_client = TestClient(
        create_app(repository, message_reader=_reply_content, reply_actions=actions)
    )

    response = reply_client.get("/inbox", headers=_identity_headers())

    assert response.status_code == 200
    assert "Odpowiedź została wysłana" in response.text
    assert 'aria-label="Krótka odpowiedź"' not in response.text
    assert "Zatwierdź i wyślij" not in response.text


class StubDraftActions:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, dict[str, object]]] = []
        self.conflict = False

    def _record(self, action: str, draft_id: int, values: dict[str, object]) -> None:
        if self.conflict:
            raise DraftActionConflict("stale")
        self.calls.append((action, draft_id, values))

    def edit(self, draft_id: int, **values: object) -> None:
        self._record("edit", draft_id, values)

    def approve(self, draft_id: int, **values: object) -> None:
        self._record("approve", draft_id, values)

    def reject(self, draft_id: int, **values: object) -> None:
        self._record("reject", draft_id, values)


def _form_token(page: str, action: str) -> str:
    match = re.search(
        rf'action="/drafts/7/{action}".*?name="action_token" value="([a-f0-9]{{64}})"',
        page,
        re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_inbox_exposes_audited_draft_actions_when_enabled(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(create_app(repository, draft_actions=actions))

    response = action_client.get("/inbox", headers=_identity_headers())

    assert response.status_code == 200
    assert "Zatwierdź i wyślij" in response.text
    assert "Edytuj szkic" in response.text
    assert "Odrzuć" in response.text
    assert "rew. 2" in response.text
    assert response.text.count('method="post"') == 3


def test_draft_edit_uses_viewed_revision_and_authenticated_actor(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(create_app(repository, draft_actions=actions))
    page = action_client.get("/inbox", headers=_identity_headers()).text

    response = action_client.post(
        "/drafts/7/edit",
        headers=_identity_headers(),
        data={
            "subject": "Nowy temat",
            "body": "Nowa treść",
            "expected_revision": "1",
            "action_token": _form_token(page, "edit"),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=edited"
    assert actions.calls == [
        (
            "edit",
            7,
            {
                "subject": "Nowy temat",
                "body": "Nowa treść",
                "expected_revision": 1,
                "via": "secretariat-board:owner@example.com",
            },
        )
    ]


def test_draft_approval_rejects_invalid_csrf_without_calling_rail(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(create_app(repository, draft_actions=actions))

    response = action_client.post(
        "/drafts/7/approve",
        headers=_identity_headers(),
        data={"expected_revision": "1", "action_token": "0" * 64},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert actions.calls == []


def test_draft_approval_calls_canonical_rail_once(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(create_app(repository, draft_actions=actions))
    page = action_client.get("/inbox", headers=_identity_headers()).text

    response = action_client.post(
        "/drafts/7/approve",
        headers=_identity_headers(),
        data={"expected_revision": "1", "action_token": _form_token(page, "approve")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=sent"
    assert actions.calls == [
        (
            "approve",
            7,
            {"expected_revision": 1, "via": "secretariat-board:owner@example.com"},
        )
    ]


def test_action_token_remains_valid_across_app_restart(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    credential = tmp_path / "action-token-secret"
    credential.write_bytes(b"persistent-test-action-secret-32-bytes")
    monkeypatch.setenv("SECRETARIAT_ACTION_SECRET_FILE", str(credential))

    first_app = TestClient(create_app(repository, draft_actions=StubDraftActions()))
    page = first_app.get("/", headers=_identity_headers()).text
    token = _form_token(page, "approve")

    restarted_actions = StubDraftActions()
    restarted_app = TestClient(create_app(repository, draft_actions=restarted_actions))
    response = restarted_app.post(
        "/drafts/7/approve",
        headers=_identity_headers(),
        data={"expected_revision": "1", "action_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert [call[0] for call in restarted_actions.calls] == ["approve"]


def test_configured_action_token_secret_fails_closed_when_too_short(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    credential = tmp_path / "action-token-secret"
    credential.write_text("too-short")
    monkeypatch.setenv("SECRETARIAT_ACTION_SECRET_FILE", str(credential))

    with pytest.raises(RuntimeError, match="too short"):
        create_app(repository, draft_actions=StubDraftActions())


@pytest.mark.parametrize("origin", ["https://secretariat.example.test", "null"])
def test_draft_approval_accepts_same_site_browser_origin_behind_local_http_proxy(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(
        create_app(repository, draft_actions=actions),
        base_url="http://secretariat.example.test",
    )
    page = action_client.get("/inbox", headers=_identity_headers()).text

    response = action_client.post(
        "/drafts/7/approve",
        headers={
            **_identity_headers(),
            "origin": origin,
            "sec-fetch-site": "same-origin",
        },
        data={"expected_revision": "1", "action_token": _form_token(page, "approve")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=sent"
    assert [call[0] for call in actions.calls] == ["approve"]


@pytest.mark.parametrize(
    ("origin", "fetch_site"),
    [
        ("https://attacker.example", "cross-site"),
        ("https://secretariat.example.test.attacker.example", "same-origin"),
        ("https://secretariat.example.test:444", "same-origin"),
        ("null", "cross-site"),
        ("https://secretariat.example.test/path", "same-origin"),
        ("https://secretariat.example.test", "cross-site"),
    ],
)
def test_draft_approval_rejects_cross_origin_request_with_valid_action_token(
    repository: StubRepository,
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
    fetch_site: str,
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    action_client = TestClient(
        create_app(repository, draft_actions=actions),
        base_url="http://secretariat.example.test",
    )
    page = action_client.get("/inbox", headers=_identity_headers()).text

    response = action_client.post(
        "/drafts/7/approve",
        headers={**_identity_headers(), "origin": origin, "sec-fetch-site": fetch_site},
        data={"expected_revision": "1", "action_token": _form_token(page, "approve")},
        follow_redirects=False,
    )

    assert response.status_code == 403
    assert actions.calls == []


def test_stale_draft_action_requires_owner_to_read_again(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    actions = StubDraftActions()
    actions.conflict = True
    action_client = TestClient(create_app(repository, draft_actions=actions))
    page = action_client.get("/inbox", headers=_identity_headers()).text

    response = action_client.post(
        "/drafts/7/reject",
        headers=_identity_headers(),
        data={"expected_revision": "1", "action_token": _form_token(page, "reject")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/inbox?notice=stale"
    assert actions.calls == []


def test_message_cache_is_not_read_outside_inbox(
    repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    calls: list[str] = []

    def unavailable_reader(message_id: str) -> MessageContent:
        calls.append(message_id)
        return MessageContent(registry_id=message_id, available=False)

    dashboard_client = TestClient(create_app(repository, message_reader=unavailable_reader))

    response = dashboard_client.get("/performance", headers=_identity_headers())

    assert response.status_code == 200
    assert calls == []


def test_page_uses_last_good_snapshot_during_database_failure(
    client: TestClient, repository: StubRepository
) -> None:
    fresh = client.get("/", headers=_identity_headers())
    repository.fail = True

    stale = client.get("/cases", headers=_identity_headers())

    assert fresh.status_code == 200
    assert stale.status_code == 200
    assert stale.headers["x-secretariat-data-state"] == "stale"
    assert stale.headers["warning"] == '110 - "Response is stale"'
    assert "Dane mogą być nieaktualne" in stale.text
    assert "Złożyć JPK" in stale.text


def test_snapshot_survives_application_restart(
    tmp_path, repository: StubRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "dashboard.json"
    monkeypatch.setenv("SECRETARIAT_ALLOWED_LOGINS", "owner@example.com")
    monkeypatch.setenv("SECRETARIAT_TRUSTED_PROXY_IPS", "testclient")
    monkeypatch.setenv("SECRETARIAT_SNAPSHOT_FILE", str(snapshot))
    first_client = TestClient(create_app(repository))
    assert first_client.get("/", headers=_identity_headers()).status_code == 200
    assert snapshot.stat().st_mode & 0o777 == 0o600

    repository.fail = True
    restarted_client = TestClient(create_app(repository))
    stale = restarted_client.get("/", headers=_identity_headers())

    assert stale.status_code == 200
    assert stale.headers["x-secretariat-data-state"] == "stale"


def test_dashboard_page_escapes_database_content(
    client: TestClient, repository: StubRepository
) -> None:
    repository.dashboard_subject = '<script>alert("x")</script>'

    response = client.get("/", headers=_identity_headers())

    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_stylesheet_contains_no_business_data(client: TestClient) -> None:
    response = client.get("/assets/app.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "client@example.com" not in response.text
