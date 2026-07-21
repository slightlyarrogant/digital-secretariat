"""Public response contracts for the Secretariat control plane."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class StrictResponse(BaseModel):
    """Base response that rejects accidental contract drift."""

    model_config = ConfigDict(extra="forbid")


class CoverageSummary(StrictResponse):
    companies: int = Field(ge=0)
    registered_clients: int = Field(ge=0)


class InboundSummary(StrictResponse):
    received: int = Field(ge=0)
    unmatched: int = Field(ge=0)
    failed: int = Field(ge=0)


class CaseSummary(StrictResponse):
    open: int = Field(ge=0)
    overdue: int = Field(ge=0)
    due_within_7_days: int = Field(ge=0)
    missing_controls: int = Field(ge=0)


class ApprovalSummary(StrictResponse):
    pending: int = Field(ge=0)
    overdue: int = Field(ge=0)
    failed: int = Field(ge=0)


class GuestSummary(StrictResponse):
    active: int = Field(ge=0)
    overdue: int = Field(ge=0)
    incomplete: int = Field(ge=0)


class FreshnessSummary(StrictResponse):
    last_inbound_at: datetime | None
    last_send_attempt_at: datetime | None


class OperationalOverview(StrictResponse):
    schema_version: str = "1.0"
    generated_at: datetime
    window_started_at: datetime
    coverage: CoverageSummary
    inbound: InboundSummary
    cases: CaseSummary
    approvals: ApprovalSummary
    guests: GuestSummary
    freshness: FreshnessSummary


class DeadlineItem(StrictResponse):
    id: int
    company_id: int
    company_name: str
    title: str
    owner: str
    due_date: date
    state: str | None
    category: str | None


class ApprovalItem(StrictResponse):
    id: int
    company_name: str | None
    to_address: str
    subject: str
    status: str
    due_at: datetime | None
    created_at: datetime
    body_text: str = ""
    revision_count: int = 0
    error: str | None = None


class InboundItem(StrictResponse):
    id: str
    company_name: str | None
    sender_email: str
    subject: str
    processing_status: str
    received_at: datetime
    response_sent: bool = False


class GuestItem(StrictResponse):
    id: int
    display_name: str
    email: str
    stage: str
    next_action: str | None
    next_action_owner: str | None
    next_action_due: date | None
    last_event: str | None


class ClientItem(StrictResponse):
    company_id: int
    company_name: str
    effective_status: str
    owner: str | None
    service_scope: dict[str, Any]
    contract_ok: bool = Field(validation_alias=AliasChoices("contract_ok", "contract_present"))
    vat_status: str | None
    ksef_token_present: bool
    mismatch_vat: bool
    mismatch_status: bool


class MailVolumePoint(StrictResponse):
    day: date
    inbound: int = Field(ge=0)
    invoice_channel: int = Field(ge=0)
    processed: int = Field(ge=0)
    failed: int = Field(ge=0)


class ResponseVolumePoint(StrictResponse):
    day: date
    linked: int = Field(ge=0)
    formatted_approved: int = Field(ge=0)
    automatic: int = Field(ge=0)
    unclassified: int = Field(ge=0)


class DeliveryVolumePoint(StrictResponse):
    day: date
    accepted: int = Field(ge=0)
    failed: int = Field(ge=0)


class OutreachVolumePoint(StrictResponse):
    day: date
    sent: int = Field(ge=0)
    replied: int = Field(ge=0)


class InvoiceAutomationSummary(StrictResponse):
    window_days: int = Field(default=30, ge=1)
    inbound_total: int = Field(ge=0)
    received: int = Field(ge=0)
    processed: int = Field(ge=0)
    failed: int = Field(ge=0)
    share_of_inbound: float | None = Field(default=None, ge=0, le=100)
    processing_rate: float | None = Field(default=None, ge=0, le=100)
    touchless_rate: float | None = Field(default=None, ge=0, le=100)
    daily: list[MailVolumePoint] = Field(default_factory=list)


class ResponseAutomationSummary(StrictResponse):
    window_days: int = Field(default=30, ge=1)
    sent: int = Field(ge=0)
    formatted_approved: int = Field(ge=0)
    automatic: int | None = Field(default=None, ge=0)
    unclassified_origin: int = Field(ge=0)
    classification_coverage: float | None = Field(default=None, ge=0, le=100)
    daily: list[ResponseVolumePoint] = Field(default_factory=list)


class OutboundDeliverySummary(StrictResponse):
    window_days: int = Field(default=30, ge=1)
    accepted: int = Field(ge=0)
    failed: int = Field(ge=0)
    bounced: int = Field(ge=0)
    daily: list[DeliveryVolumePoint] = Field(default_factory=list)


class CampaignVariantSummary(StrictResponse):
    campaign: str
    variant: str | None
    sent: int = Field(ge=0)
    replied: int = Field(ge=0)
    converted: int = Field(ge=0)
    unsubscribed: int = Field(ge=0)
    reply_rate: float | None = Field(default=None, ge=0, le=100)
    conversion_rate: float | None = Field(default=None, ge=0, le=100)


class OutreachSummary(StrictResponse):
    available: bool
    window_days: int = Field(default=90, ge=1)
    sent: int = Field(ge=0)
    replied: int = Field(ge=0)
    human_replies: int = Field(ge=0)
    registrations: int = Field(ge=0)
    converted: int = Field(ge=0)
    unsubscribed: int = Field(ge=0)
    failed: int = Field(ge=0)
    reply_rate: float | None = Field(default=None, ge=0, le=100)
    conversion_rate: float | None = Field(default=None, ge=0, le=100)
    variants: list[CampaignVariantSummary]
    daily: list[OutreachVolumePoint] = Field(default_factory=list)


class PerformanceSummary(StrictResponse):
    invoices: InvoiceAutomationSummary
    responses: ResponseAutomationSummary
    delivery: OutboundDeliverySummary
    outreach: OutreachSummary


class MessageAttachment(StrictResponse):
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)


class MessageContent(StrictResponse):
    registry_id: str
    available: bool
    mailbox: str | None = None
    folder: str | None = None
    from_address: str | None = None
    to_address: str | None = None
    sent_at: str | None = None
    subject: str | None = None
    body_text: str | None = None
    attachments: list[MessageAttachment] = Field(default_factory=list)


class EvidenceRef(StrictResponse):
    source_type: Literal["email_draft", "obligation", "inbound_email", "guest_register"]
    source_id: str
    label: str


class AttentionItem(StrictResponse):
    id: str
    kind: Literal["decision", "deadline", "inbound", "relationship"]
    severity: Literal["critical", "warning", "neutral"]
    title: str
    company_name: str | None
    why_now: str
    recommendation: str
    default_action: str
    owner: str | None
    due_at: datetime | None = None
    due_on: date | None = None
    evidence: EvidenceRef


class OperationalDashboard(StrictResponse):
    schema_version: str = "1.4"
    overview: OperationalOverview
    attention: list[AttentionItem]
    deadlines: list[DeadlineItem]
    approvals: list[ApprovalItem]
    inbound: list[InboundItem]
    guests: list[GuestItem]
    clients: list[ClientItem]
    performance: PerformanceSummary


class LiveStatus(StrictResponse):
    status: str = "alive"
    service: str = "digital-secretariat"
    version: str


class ReadyStatus(StrictResponse):
    status: str
    service: str = "digital-secretariat"
