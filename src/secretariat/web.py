"""Server-rendered, exception-first workspace for the owner."""

import html
import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal

from src.secretariat.auth import TailnetPrincipal
from src.secretariat.schemas import (
    ApprovalItem,
    AttentionItem,
    ClientItem,
    MessageContent,
    OperationalDashboard,
)

WorkspaceView = Literal[
    "today",
    "inbox",
    "cases",
    "relationships",
    "calendar",
    "performance",
    "system",
]

_VIEW_PATHS: dict[WorkspaceView, str] = {
    "today": "/",
    "inbox": "/inbox",
    "cases": "/cases",
    "relationships": "/relationships",
    "calendar": "/calendar",
    "performance": "/performance",
    "system": "/system",
}

_VIEW_TITLES: dict[WorkspaceView, str] = {
    "today": "Dzisiaj",
    "inbox": "Skrzynka",
    "cases": "Sprawy",
    "relationships": "Relacje",
    "calendar": "Kalendarz",
    "performance": "Wyniki",
    "system": "System",
}

_CATEGORY_LABELS = {
    "cit_advance": "CIT",
    "pit4": "PIT-4",
    "jpk": "JPK_V7M",
    "jpk_vat": "JPK_V7M",
    "jpk_v7m": "JPK_V7M",
}

_STATUS_LABELS = {
    "active": "Klient",
    "klient": "Klient",
    "onboarding": "Wdrożenie",
    "suspended": "Wstrzymany",
    "prospect": "Prospekt",
    "prospekt": "Prospekt",
    "lead": "Prospekt",
    "unknown": "Brak statusu",
    "pending_approval": "Czeka na decyzję",
    "pending": "Oczekuje",
    "waiting": "Oczekuje",
    "failed": "Błąd",
    "processed": "Obsłużona",
}

_OWNER_LABELS = {
    "us": "Sekretariat",
    "sekretariat": "Sekretariat",
    "owner": "Właściciel",
    "owner-1": "Właściciel",
    "właściciel": "Właściciel",
}

_KIND_LABELS = {
    "decision": "Decyzja",
    "deadline": "Termin",
    "inbound": "Nowy wpływ",
    "relationship": "Relacja",
}

_WEEKDAY_LABELS = (
    "Poniedziałek",
    "Wtorek",
    "Środa",
    "Czwartek",
    "Piątek",
    "Sobota",
    "Niedziela",
)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "brak terminu"


def _moment(value: datetime | None) -> str:
    return value.astimezone().strftime("%d.%m, %H:%M") if value else "brak danych"


def _owner(value: str | None) -> str:
    if not value:
        return "Nieprzypisane"
    return _OWNER_LABELS.get(value.casefold(), value)


def _category(value: str | None) -> str:
    if not value:
        return "Sprawa"
    return _CATEGORY_LABELS.get(value.casefold(), value.replace("_", " ").upper())


def _status(value: str) -> str:
    return _STATUS_LABELS.get(value.casefold(), value.replace("_", " ").capitalize())


def _initials(value: str) -> str:
    words = [word for word in value.replace(".", " ").split() if word]
    return "".join(word[0] for word in words[:2]).upper() or "?"


def _empty(message: str) -> str:
    return (
        '<div class="empty-state"><span class="empty-mark">✓</span>'
        f"<div><strong>Wszystko pod kontrolą</strong><p>{_esc(message)}</p></div></div>"
    )


def _message_snippet(value: str | None, *, limit: int = 320) -> str:
    compact = re.sub(r"\s+", " ", value or "").strip()
    if not compact:
        return "Brak tekstowej treści wiadomości."
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    snippet = " ".join(sentences[:3])
    shortened = len(sentences) > 3 or len(snippet) > limit
    if len(snippet) > limit:
        candidate = snippet[: limit - 1].rsplit(" ", 1)[0]
        snippet = candidate or snippet[: limit - 1]
    return f"{snippet}…" if shortened else snippet


def _reply_subject(value: str | None) -> str:
    subject = re.sub(r"\s+", " ", value or "").strip()
    if subject.casefold().startswith("re:"):
        return subject[:998]
    return f"Re: {subject}"[:998]


def _attachment_count_label(count: int) -> str:
    if count == 1:
        return "1 załącznik"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return f"{count} załączniki"
    return f"{count} załączników"


def _inline_attachments(content: MessageContent) -> str:
    if not content.attachments:
        return ""
    rows = "".join(
        '<div class="mail-attachment">'
        f'<span class="attachment-type">{_esc(item.filename.rsplit(".", 1)[-1].upper()[:3])}</span>'
        f"<div><strong>{_esc(item.filename)}</strong>"
        f"<span>{_esc(item.content_type)} · {item.size_bytes / 1024:.1f} KB</span></div></div>"
        for item in content.attachments
    )
    return f'<div class="mail-attachments"><span class="eyebrow">Załączniki</span>{rows}</div>'


def _days_label(value: int) -> str:
    return "1 dzień" if value == 1 else f"{value} dni"


def _attention_lead(total: int, critical: int) -> str:
    if critical == 1:
        return "1 pilna sprawa wymaga reakcji."
    if critical % 10 in (2, 3, 4) and critical % 100 not in (12, 13, 14):
        return f"{critical} pilne sprawy wymagają reakcji."
    if critical:
        return f"{critical} pilnych spraw wymaga reakcji."
    if total == 1:
        return "1 sprawa wymaga uwagi, bez alarmów krytycznych."
    if total % 10 in (2, 3, 4) and total % 100 not in (12, 13, 14):
        return f"{total} sprawy wymagają uwagi, bez alarmów krytycznych."
    if total:
        return f"{total} spraw wymaga uwagi, bez alarmów krytycznych."
    return "Nie ma spraw wymagających Twojej reakcji."


def _relative_date(value: date, today: date) -> tuple[str, str]:
    days = (value - today).days
    if days < 0:
        return "critical", f"{_days_label(abs(days))} po terminie"
    if days == 0:
        return "critical", "Dzisiaj"
    if days <= 3:
        return "warning", f"Za {_days_label(days)}"
    return "neutral", f"Za {_days_label(days)}"


def _attention_due(item: AttentionItem, today: date) -> tuple[str, str]:
    if item.due_on:
        return _relative_date(item.due_on, today)
    if item.due_at:
        day_tone, relative = _relative_date(item.due_at.astimezone().date(), today)
        return day_tone, f"{relative}, {item.due_at.astimezone().strftime('%H:%M')}"
    return "neutral", "Bez terminu"


def _attention_rows(items: list[AttentionItem], today: date, limit: int = 5) -> str:
    rows: list[str] = []
    for item in items[:limit]:
        due_tone, due_label = _attention_due(item, today)
        company = item.company_name or "Bez przypisania"
        if item.kind == "decision":
            rows.append(
                f'<a class="attention-item attention-link {item.severity}" '
                f'href="#draft-{_esc(item.evidence.source_id)}">'
                f'<span class="priority-line {item.severity}"></span>'
                '<div class="attention-copy">'
                f'<span class="attention-meta">{_esc(_KIND_LABELS[item.kind])} · {_esc(company)}</span>'
                f"<strong>{_esc(item.title)}</strong>"
                f"<p>{_esc(item.why_now)}</p>"
                "</div>"
                '<div class="attention-side">'
                f'<span class="due {due_tone}">{_esc(due_label)}</span>'
                '<span class="attention-jump">Otwórz</span>'
                "</div></a>"
            )
            continue
        rows.append(
            f'<details class="attention-item {item.severity}">'
            "<summary>"
            f'<span class="priority-line {item.severity}"></span>'
            '<div class="attention-copy">'
            f'<span class="attention-meta">{_esc(_KIND_LABELS[item.kind])} · {_esc(company)}</span>'
            f"<strong>{_esc(item.title)}</strong>"
            f"<p>{_esc(item.why_now)}</p>"
            "</div>"
            '<div class="attention-side">'
            f'<span class="due {due_tone}">{_esc(due_label)}</span>'
            f'<span class="disclosure" aria-hidden="true">›</span>'
            "</div>"
            "</summary>"
            '<div class="attention-detail">'
            "<div><span>Rekomendacja</span>"
            f"<strong>{_esc(item.recommendation)}</strong></div>"
            "<div><span>Bez decyzji</span>"
            f"<strong>{_esc(item.default_action)}</strong></div>"
            "<div><span>Odpowiedzialność</span>"
            f"<strong>{_esc(_owner(item.owner))}</strong></div>"
            "<div><span>Dowód źródłowy</span>"
            f"<strong>{_esc(item.evidence.label)}</strong></div>"
            "</div>"
            "</details>"
        )
    return "".join(rows) or _empty("Nie ma spraw wymagających uwagi właściciela.")


def _deadline_rows(data: OperationalDashboard, *, limit: int | None = None) -> str:
    rows: list[str] = []
    today = data.overview.generated_at.astimezone().date()
    items = data.deadlines[:limit] if limit is not None else data.deadlines
    for item in items:
        tone, relative = _relative_date(item.due_date, today)
        rows.append(
            '<div class="record-row deadline-row">'
            f'<div class="company-token">{_esc(_initials(item.company_name))}</div>'
            '<div class="record-primary">'
            f"<strong>{_esc(item.title)}</strong>"
            f"<span>{_esc(item.company_name)} · {_esc(_category(item.category))}</span></div>"
            f'<div class="record-owner">{_esc(_owner(item.owner))}</div>'
            '<div class="record-date">'
            f'<span class="due {tone}">{_esc(relative)}</span>'
            f"<small>{_date(item.due_date)}</small></div>"
            "</div>"
        )
    return "".join(rows) or _empty("Brak terminów w najbliższych 14 dniach.")


def _draft_controls(item: ApprovalItem, tokens: Mapping[str, str]) -> str:
    revision = item.revision_count
    hidden_revision = f'<input type="hidden" name="expected_revision" value="{revision}">'

    if item.status == "failed":
        return (
            '<div class="draft-actions">'
            f'<form method="post" action="/drafts/{item.id}/approve">{hidden_revision}'
            f'<input type="hidden" name="action_token" value="{_esc(tokens["approve"])}">'
            '<button class="button primary" type="submit">Ponów wysyłkę</button></form>'
            "</div>"
        )
    if item.status != "pending_approval":
        return '<p class="draft-locked">Ten stan nie obsługuje decyzji z tablicy.</p>'
    return (
        '<div class="draft-actions">'
        f'<form method="post" action="/drafts/{item.id}/approve">{hidden_revision}'
        f'<input type="hidden" name="action_token" value="{_esc(tokens["approve"])}">'
        '<button class="button primary" type="submit">Zatwierdź i wyślij</button></form>'
        f'<form method="post" action="/drafts/{item.id}/reject">{hidden_revision}'
        f'<input type="hidden" name="action_token" value="{_esc(tokens["reject"])}">'
        '<button class="button danger" type="submit">Odrzuć</button></form>'
        "</div>"
        '<details class="draft-editor">'
        "<summary>Edytuj szkic</summary>"
        f'<form method="post" action="/drafts/{item.id}/edit">{hidden_revision}'
        f'<input type="hidden" name="action_token" value="{_esc(tokens["edit"])}">'
        "<label><span>Temat</span>"
        f'<input name="subject" required maxlength="998" value="{_esc(item.subject)}"></label>'
        "<label><span>Treść</span>"
        f'<textarea name="body" required maxlength="500000">{_esc(item.body_text)}</textarea></label>'
        '<div class="editor-actions"><button class="button primary" type="submit">'
        "Zapisz zmiany</button></div></form></details>"
    )


def _approval_rows(
    data: OperationalDashboard,
    action_tokens: Mapping[int, Mapping[str, str]],
) -> str:
    rows: list[str] = []
    for item in data.approvals:
        tone = "critical" if item.status == "failed" else "warning"
        tokens = action_tokens.get(item.id)
        controls = _draft_controls(item, tokens) if tokens else ""
        error = (
            '<div class="draft-error" role="alert"><strong>Błąd ostatniej próby</strong>'
            f"<p>{_esc(item.error or 'Brak szczegółów błędu w rejestrze.')}</p></div>"
            if item.status == "failed"
            else ""
        )
        rows.append(
            f'<details class="mail-item {tone}" id="draft-{item.id}" name="secretariat-mail">'
            '<summary class="mail-summary approval-mail">'
            f'<div><span class="status {tone}">{_esc(_status(item.status))}</span></div>'
            '<div class="mail-primary">'
            f"<strong>{_esc(item.subject)}</strong>"
            f"<span>Do: {_esc(item.to_address)}</span>"
            f'<p class="mail-snippet">{_esc(_message_snippet(item.body_text))}</p></div>'
            '<div class="mail-context">'
            f'<strong>{_esc(item.company_name or "Bez przypisania")}</strong>'
            f"<span>{_moment(item.created_at)}</span></div>"
            '<span class="mail-disclosure" aria-hidden="true">›</span>'
            "</summary>"
            '<div class="mail-expanded">'
            '<div class="mail-expanded-head"><div><span>Odbiorca</span>'
            f"<strong>{_esc(item.to_address)}</strong></div><div><span>Stan</span>"
            f"<strong>{_esc(_status(item.status))}</strong></div><div><span>Wersja</span>"
            f"<strong>rew. {item.revision_count + 1}</strong></div></div>"
            '<div class="mail-body-label"><span class="eyebrow">Treść szkicu</span>'
            '<span class="private-label">Przed wysłaniem</span></div>'
            f'<pre class="mail-inline-body">{_esc(item.body_text or "(brak treści tekstowej)")}</pre>'
            f"{error}{controls}</div></details>"
        )
    return "".join(rows) or _empty("Brak wiadomości oczekujących na decyzję.")


def _inbound_rows(
    data: OperationalDashboard,
    message_previews: Mapping[str, MessageContent],
    reply_tokens: Mapping[str, str],
) -> str:
    rows: list[str] = []
    for item in data.inbound:
        unmatched = item.company_name is None
        failed = item.processing_status == "failed"
        tone = "critical" if failed else ("warning" if unmatched else "ok")
        label = "Nieprzypisana" if unmatched and not failed else _status(item.processing_status)
        content = message_previews.get(item.id)
        available = bool(content and content.available)
        snippet = (
            _message_snippet(content.body_text)
            if available and content is not None
            else "Treść nie została jeszcze zarchiwizowana."
        )
        if available and content is not None:
            attachment_label = _attachment_count_label(len(content.attachments))
            reply = ""
            if item.response_sent:
                reply = (
                    '<div class="reply-complete"><span class="signal ok"></span>'
                    "<strong>Odpowiedź została wysłana</strong></div>"
                )
            elif token := reply_tokens.get(item.id):
                reply = (
                    '<section class="reply-composer" aria-label="Krótka odpowiedź">'
                    '<header><div><span class="eyebrow">Krótka odpowiedź</span>'
                    f"<h3>Do: {_esc(item.sender_email)}</h3></div>"
                    '<span class="private-label">Przed wysłaniem</span></header>'
                    f'<form method="post" action="/inbox/{_esc(item.id)}/reply">'
                    f'<input type="hidden" name="action_token" value="{_esc(token)}">'
                    "<label><span>Temat</span>"
                    f'<input name="subject" required maxlength="998" '
                    f'value="{_esc(_reply_subject(item.subject))}"></label>'
                    "<label><span>Treść</span>"
                    '<textarea name="body" required maxlength="10000" rows="4"></textarea></label>'
                    '<div class="reply-actions">'
                    '<button class="button" type="submit" name="intent" value="queue">'
                    "Zapisz szkic</button>"
                    '<button class="button primary" type="submit" name="intent" value="send">'
                    "Zatwierdź i wyślij</button></div></form></section>"
                )
            expanded = (
                '<div class="mail-expanded">'
                '<div class="mail-expanded-head"><div><span>Od</span>'
                f"<strong>{_esc(content.from_address or item.sender_email)}</strong></div>"
                "<div><span>Skrzynka</span>"
                f"<strong>{_esc(content.mailbox or 'brak danych')}</strong></div>"
                f"<div><span>Załączniki</span><strong>{_esc(attachment_label)}</strong></div></div>"
                '<div class="mail-body-label"><span class="eyebrow">Pełna wiadomość</span>'
                '<span class="private-label">Treść prywatna</span></div>'
                f'<pre class="mail-inline-body">{_esc(content.body_text or "(brak treści tekstowej)")}</pre>'
                f"{_inline_attachments(content)}{reply}</div>"
            )
        else:
            expanded = (
                '<div class="mail-expanded mail-cache-missing"><strong>Treść jeszcze niedostępna.</strong>'
                "<p>Rejestr wpływu istnieje, ale prywatny cache nie zawiera jeszcze tej wiadomości.</p></div>"
            )
        rows.append(
            '<details class="mail-item" name="secretariat-mail">'
            '<summary class="mail-summary inbound-mail">'
            '<div class="record-time">'
            f'<strong>{item.received_at.astimezone().strftime("%H:%M")}</strong>'
            f'<span>{item.received_at.astimezone().strftime("%d.%m")}</span></div>'
            '<div class="mail-primary">'
            f"<strong>{_esc(item.subject)}</strong>"
            f"<span>{_esc(item.sender_email)}</span>"
            f'<p class="mail-snippet">{_esc(snippet)}</p></div>'
            f'<div class="mail-context"><strong>{_esc(item.company_name or "Nowa relacja")}</strong>'
            f'<span>{"Treść dostępna" if available else "Oczekuje na treść"}</span></div>'
            f'<div class="mail-state"><span class="status {tone}">{_esc(label)}</span>'
            '<span class="mail-disclosure" aria-hidden="true">›</span></div>'
            f"</summary>{expanded}</details>"
        )
    return "".join(rows) or _empty("Brak zarejestrowanego wpływu.")


def _guest_rows(data: OperationalDashboard) -> str:
    rows: list[str] = []
    today = data.overview.generated_at.astimezone().date()
    for item in data.guests:
        incomplete = not item.next_action or not item.next_action_owner or not item.next_action_due
        overdue = bool(item.next_action_due and item.next_action_due < today)
        tone = "critical" if incomplete or overdue else "neutral"
        due = "Uzupełnij krok" if incomplete else _date(item.next_action_due)
        rows.append(
            '<div class="record-row relationship-row">'
            f'<div class="company-token">{_esc(_initials(item.display_name))}</div>'
            '<div class="record-primary">'
            f"<strong>{_esc(item.display_name)}</strong><span>{_esc(item.email)}</span></div>"
            '<div class="record-context">'
            f'<strong>{_esc(item.next_action or "Brak kolejnego kroku")}</strong>'
            f"<span>{_esc(_owner(item.next_action_owner))}</span></div>"
            f'<div><span class="status {tone}">{_esc(due)}</span></div>'
            "</div>"
        )
    return "".join(rows) or _empty("Brak aktywnych relacji przedklienckich.")


def _client_health(item: ClientItem) -> tuple[str, str]:
    if item.effective_status.casefold() in {"prospect", "prospekt", "lead"}:
        return "neutral", "Pipeline"
    if item.mismatch_vat or item.mismatch_status:
        return "critical", "Wymaga weryfikacji"
    missing = sum((not item.contract_ok, not item.ksef_token_present))
    return ("warning", "Braki w kotwicach") if missing else ("ok", "Kompletne")


def _client_rows(items: list[ClientItem]) -> str:
    rows: list[str] = []
    for item in items:
        tone, health = _client_health(item)
        vat_ok = not item.mismatch_vat
        rows.append(
            '<div class="record-row client-row">'
            f'<div class="company-token">{_esc(_initials(item.company_name))}</div>'
            '<div class="record-primary">'
            f"<strong>{_esc(item.company_name)}</strong>"
            f"<span>{_esc(_owner(item.owner))}</span></div>"
            f'<div><span class="status neutral">{_esc(_status(item.effective_status))}</span></div>'
            '<div class="anchor-list">'
            f'<span class="anchor {"ok" if item.contract_ok else "missing"}">Umowa</span>'
            f'<span class="anchor {"ok" if vat_ok else "missing"}">VAT</span>'
            f'<span class="anchor {"ok" if item.ksef_token_present else "missing"}">KSeF</span></div>'
            f'<div><span class="status {tone}">{_esc(health)}</span></div>'
            "</div>"
        )
    return "".join(rows) or _empty("Ta grupa jest pusta.")


def _section_head(eyebrow: str, title: str, count: int, description: str = "") -> str:
    copy = f"<p>{_esc(description)}</p>" if description else ""
    return (
        '<div class="section-head"><div>'
        f'<span class="eyebrow">{_esc(eyebrow)}</span><h2>{_esc(title)}</h2>{copy}</div>'
        f'<span class="count">{count}</span></div>'
    )


def _page_head(kicker: str, title: str, description: str) -> str:
    return (
        '<header class="page-head">'
        f'<span class="eyebrow">{_esc(kicker)}</span><h1>{_esc(title)}</h1>'
        f"<p>{_esc(description)}</p></header>"
    )


def _today_view(
    data: OperationalDashboard,
    action_tokens: Mapping[int, Mapping[str, str]],
) -> str:
    overview = data.overview
    today = overview.generated_at.astimezone().date()
    focus = data.attention[:5]
    critical = sum(item.severity == "critical" for item in data.attention)
    lead = _attention_lead(len(data.attention), critical)
    more = ""
    if len(data.attention) > len(focus):
        more = (
            '<div class="section-action">'
            f'<a href="/inbox">Zobacz pozostałe {len(data.attention) - len(focus)} spraw</a></div>'
        )
    return (
        _page_head(
            f"{_WEEKDAY_LABELS[today.weekday()]}, {today.strftime('%d.%m.%Y')}",
            "Dzisiaj",
            lead,
        )
        + '<div class="today-grid"><div class="focus-column">'
        + '<section class="workspace-section decision-queue">'
        + _section_head("Bramka wysyłki", "Do decyzji", len(data.approvals))
        + f'<div class="record-list">{_approval_rows(data, action_tokens)}</div></section>'
        + '<section class="workspace-section">'
        + _section_head("Kolejka właściciela", "Wymaga uwagi", len(data.attention))
        + f'<div class="attention-list">{_attention_rows(focus, today)}</div>{more}</section>'
        + '<section class="workspace-section upcoming">'
        + _section_head(
            "Horyzont 14 dni",
            "Najbliższe terminy",
            len(data.deadlines),
            "Kolejność według terminu, nie według klienta.",
        )
        + f'<div class="record-list">{_deadline_rows(data, limit=5)}</div>'
        + '<div class="section-action"><a href="/calendar">Otwórz kalendarz</a></div></section>'
        + '</div><aside class="day-rail">'
        + '<section class="pulse"><span class="eyebrow">Puls dnia</span>'
        + '<dl class="pulse-list">'
        + f'<div><dt>Po terminie</dt><dd class="{"bad" if overview.cases.overdue else ""}">{overview.cases.overdue}</dd></div>'
        + f"<div><dt>Do decyzji</dt><dd>{overview.approvals.pending}</dd></div>"
        + f"<div><dt>Bez przypisania</dt><dd>{overview.inbound.unmatched}</dd></div>"
        + f"<div><dt>Wpływy 24h</dt><dd>{overview.inbound.received}</dd></div>"
        + "</dl></section>"
        + '<section class="trust"><span class="eyebrow">Wiarygodność</span>'
        + '<div class="trust-state"><span class="signal ok"></span><strong>Źródła dostępne</strong></div>'
        + f"<p>Ostatni wpływ: {_moment(overview.freshness.last_inbound_at)}</p>"
        + f"<p>Stan wygenerowany: {_moment(overview.generated_at)}</p>"
        + '<a href="/system">Zobacz stan systemu</a></section>'
        + "</aside></div>"
    )


def _inbox_view(
    data: OperationalDashboard,
    message_previews: Mapping[str, MessageContent],
    action_tokens: Mapping[int, Mapping[str, str]],
    reply_tokens: Mapping[str, str],
) -> str:
    return (
        _page_head(
            "Komunikacja",
            "Skrzynka",
            "Decyzje przed wysłaniem oraz cały zarejestrowany wpływ.",
        )
        + '<section class="workspace-section">'
        + _section_head("Bramka wysyłki", "Czeka na decyzję", len(data.approvals))
        + f'<div class="record-list">{_approval_rows(data, action_tokens)}</div></section>'
        + '<section class="workspace-section">'
        + _section_head("Dziennik podawczy", "Ostatni wpływ", len(data.inbound))
        + f'<div class="record-list mail-list">{_inbound_rows(data, message_previews, reply_tokens)}</div></section>'
    )


def _cases_view(data: OperationalDashboard) -> str:
    return (
        _page_head(
            "Realizacja",
            "Sprawy",
            "Otwarte obowiązki z terminem w najbliższych 14 dniach.",
        )
        + '<section class="workspace-section">'
        + _section_head("Kolejka terminów", "Obowiązki", len(data.deadlines))
        + f'<div class="record-list">{_deadline_rows(data)}</div></section>'
    )


def _relationships_view(data: OperationalDashboard) -> str:
    prospects = {
        "prospect",
        "prospekt",
        "lead",
    }
    clients = [item for item in data.clients if item.effective_status.casefold() not in prospects]
    pipeline = [item for item in data.clients if item.effective_status.casefold() in prospects]
    return (
        _page_head(
            "Portfel",
            "Relacje",
            "Klienci operacyjni, pipeline oraz relacje przedklienckie są rozdzielone.",
        )
        + '<section class="workspace-section">'
        + _section_head("Obsługiwani", "Klienci", len(clients))
        + f'<div class="record-list">{_client_rows(clients)}</div></section>'
        + '<section class="workspace-section">'
        + _section_head("Pipeline", "Prospekci", len(pipeline))
        + f'<div class="record-list">{_client_rows(pipeline)}</div></section>'
        + '<section class="workspace-section">'
        + _section_head("Przed rejestrem klienta", "Goście", len(data.guests))
        + f'<div class="record-list">{_guest_rows(data)}</div></section>'
    )


def _calendar_view(data: OperationalDashboard) -> str:
    return (
        _page_head(
            "Terminy",
            "Kalendarz",
            "Najbliższe zobowiązania w jednej chronologicznej osi.",
        )
        + '<section class="workspace-section calendar-section">'
        + _section_head("14 dni", "Oś terminów", len(data.deadlines))
        + f'<div class="record-list timeline">{_deadline_rows(data)}</div></section>'
    )


def _metric(value: int | float | None, suffix: str = "") -> str:
    if value is None:
        return '<strong class="metric-missing">Niemierzone</strong>'
    rendered = f"{value:g}" if isinstance(value, float) else str(value)
    return f"<strong>{_esc(rendered)}{_esc(suffix)}</strong>"


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator * 100 / denominator, 2)


def _sparkline(points: list[Any], key: str, tone: str) -> str:
    values = [int(getattr(point, key)) for point in points]
    if not values:
        return '<span class="sparkline-empty"></span>'
    width, height, padding = 120, 34, 3
    maximum = max(max(values), 1)
    denominator = max(len(values) - 1, 1)
    coordinates = [
        (
            padding + index * (width - 2 * padding) / denominator,
            height - padding - value * (height - 2 * padding) / maximum,
        )
        for index, value in enumerate(values)
    ]
    path = " ".join(
        f'{"M" if index == 0 else "L"}{x:.1f},{y:.1f}' for index, (x, y) in enumerate(coordinates)
    )
    return (
        f'<svg class="sparkline spark-{tone}" viewBox="0 0 {width} {height}" '
        'aria-hidden="true" preserveAspectRatio="none">'
        f'<path d="{path}" pathLength="1"></path></svg>'
    )


def _kpi_card(
    label: str,
    value: int | float | None,
    suffix: str,
    context: str,
    tone: str,
    sparkline: str,
) -> str:
    value_html = _metric(value, suffix)
    return (
        f'<article class="kpi-card kpi-{tone}">'
        f'<div class="kpi-label"><span>{_esc(label)}</span><i></i></div>'
        f'<div class="kpi-value">{value_html}</div>'
        f"<p>{_esc(context)}</p>{sparkline}</article>"
    )


def _line_chart(
    points: list[Any],
    series: tuple[tuple[str, str, str], ...],
    aria_label: str,
) -> str:
    if not points:
        return _empty("Brak szeregu czasowego dla wybranego okresu.")
    width, height = 720, 248
    left, right, top, bottom = 42, 14, 18, 34
    chart_width = width - left - right
    chart_height = height - top - bottom
    all_values = [int(getattr(point, key)) for point in points for key, _, _ in series]
    maximum = max(max(all_values, default=0), 1)
    denominator = max(len(points) - 1, 1)

    grid = ""
    for fraction in (0.0, 0.5, 1.0):
        y = top + chart_height * (1 - fraction)
        label = round(maximum * fraction)
        grid += (
            f'<line class="chart-grid-line" x1="{left}" y1="{y:.1f}" '
            f'x2="{width - right}" y2="{y:.1f}"></line>'
            f'<text class="chart-axis-label" x="0" y="{y + 4:.1f}">{label}</text>'
        )

    paths = ""
    for series_index, (key, _, tone) in enumerate(series):
        coordinates = [
            (
                left + index * chart_width / denominator,
                top + chart_height * (1 - int(getattr(point, key)) / maximum),
            )
            for index, point in enumerate(points)
        ]
        path = " ".join(
            f'{"M" if index == 0 else "L"}{x:.1f},{y:.1f}'
            for index, (x, y) in enumerate(coordinates)
        )
        if series_index == 0:
            area = (
                f"{path} L{coordinates[-1][0]:.1f},{top + chart_height:.1f} "
                f"L{coordinates[0][0]:.1f},{top + chart_height:.1f} Z"
            )
            paths += f'<path class="chart-area area-{tone}" d="{area}"></path>'
        paths += f'<path class="chart-line line-{tone}" d="{path}"></path>'

    tick_indexes = sorted({0, len(points) // 2, len(points) - 1})
    ticks = "".join(
        f'<text class="chart-date-label" x="{left + index * chart_width / denominator:.1f}" '
        f'y="{height - 7}" text-anchor="{("start" if index == 0 else "end" if index == len(points) - 1 else "middle")}">'
        f'{points[index].day.strftime("%d.%m")}</text>'
        for index in tick_indexes
    )
    legend = "".join(
        f'<span><i class="legend-{tone}"></i>{_esc(label)}</span>' for _, label, tone in series
    )
    return (
        f'<div class="chart-legend">{legend}</div>'
        f'<svg class="line-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_esc(aria_label)}" preserveAspectRatio="none">'
        f"{grid}{paths}{ticks}</svg>"
    )


def _donut(value: int, total: int, label: str, tone: str) -> str:
    percentage = _rate(value, total) or 0
    return (
        '<div class="donut-wrap">'
        '<svg class="donut" viewBox="0 0 120 120" role="img" '
        f'aria-label="{_esc(label)}: {percentage:g}%">'
        '<circle class="donut-track" cx="60" cy="60" r="46" pathLength="100"></circle>'
        f'<circle class="donut-value donut-{tone}" cx="60" cy="60" r="46" '
        f'pathLength="100" stroke-dasharray="{percentage:.2f} {100 - percentage:.2f}"></circle>'
        "</svg>"
        f"<div><strong>{percentage:g}%</strong><span>{_esc(label)}</span></div></div>"
    )


def _variant_comparison(data: OperationalDashboard) -> str:
    variants = data.performance.outreach.variants
    if not variants:
        return _empty("Brak wariantów kampanii w tym okresie.")
    maximum = max((item.reply_rate or 0 for item in variants), default=0) or 1
    rows = []
    for item in variants:
        rate = item.reply_rate or 0
        bar_width = rate * 100 / maximum
        rows.append(
            '<div class="variant-row">'
            f'<div><strong>{_esc(item.variant or "—")}</strong><span>{_esc(item.campaign)}</span></div>'
            '<div class="variant-bar">'
            '<svg viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">'
            '<rect class="variant-track" x="0" y="0" width="100" height="8" rx="4"></rect>'
            f'<rect class="variant-fill" x="0" y="0" width="{bar_width:.2f}" height="8" rx="4"></rect>'
            "</svg></div>"
            f'<div class="variant-rate"><strong>{rate:g}%</strong><span>{item.replied} / {item.sent}</span></div>'
            "</div>"
        )
    return "".join(rows)


def _funnel_stage(label: str, value: int, previous: int | None = None) -> str:
    context = (
        "Punkt wejścia"
        if previous is None
        else (f"{(_rate(value, previous) or 0):g}% poprzedniego etapu")
    )
    return (
        '<div class="funnel-stage">'
        f"<span>{_esc(label)}</span><strong>{value}</strong><small>{_esc(context)}</small></div>"
    )


def _performance_view(data: OperationalDashboard) -> str:
    performance = data.performance
    invoices = performance.invoices
    responses = performance.responses
    delivery = performance.delivery
    outreach = performance.outreach
    delivery_rate = _rate(delivery.accepted, delivery.accepted + delivery.failed)
    response_classified = responses.formatted_approved + (responses.automatic or 0)
    kpis = "".join(
        (
            _kpi_card(
                "Pipeline faktury@",
                invoices.processing_rate,
                "%",
                f"{invoices.processed} z {invoices.received} wpływów przetworzonych",
                "teal",
                _sparkline(invoices.daily, "processed", "teal"),
            ),
            _kpi_card(
                "Klasyfikacja odpowiedzi",
                responses.classification_coverage,
                "%",
                f"{response_classified} sklasyfikowanych z {responses.sent}",
                "blue",
                _sparkline(responses.daily, "linked", "blue"),
            ),
            _kpi_card(
                "Przyjęcie przez SMTP",
                delivery_rate,
                "%",
                f"{delivery.accepted} przyjętych, {delivery.failed} nieudanych prób",
                "coral",
                _sparkline(delivery.daily, "accepted", "coral"),
            ),
            _kpi_card(
                "Odpowiedzi outreach",
                outreach.reply_rate,
                "%",
                f"{outreach.human_replies} ludzkich odpowiedzi, {outreach.registrations} rejestracje",
                "yellow",
                _sparkline(outreach.daily, "sent", "yellow"),
            ),
        )
    )
    response_breakdown = (
        '<dl class="breakdown-list">'
        f'<div><dt><i class="legend-teal"></i>Automatyczne</dt><dd>{responses.automatic or 0}</dd></div>'
        f'<div><dt><i class="legend-blue"></i>Zatwierdzone</dt><dd>{responses.formatted_approved}</dd></div>'
        f'<div><dt><i class="legend-gray"></i>Nieznane</dt><dd>{responses.unclassified_origin}</dd></div>'
        "</dl>"
    )
    return (
        '<div class="performance-heading">'
        + _page_head(
            "Efektywność operacyjna",
            "Wyniki",
            "Sygnały, trendy i wynik pracy sekretariatu.",
        )
        + '<div class="period-chip"><span class="signal ok"></span>Aktualne · 30 dni</div></div>'
        + f'<section class="kpi-grid" aria-label="Kluczowe wskaźniki">{kpis}</section>'
        + '<section class="analytics-grid">'
        + '<article class="chart-panel chart-wide"><header><div><span class="eyebrow">Wpływ · 30 dni</span><h2>Ruch w sekretariacie</h2></div>'
        + f'<div class="chart-total"><strong>{invoices.inbound_total}</strong><span>wiadomości</span></div></header>'
        + _line_chart(
            invoices.daily,
            (("inbound", "Cały wpływ", "blue"), ("invoice_channel", "Kanał faktury@", "yellow")),
            "Dzienny wpływ wiadomości i kanału faktury@ z ostatnich 30 dni",
        )
        + f'<footer><span>Kanał faktury@ stanowi {_metric(invoices.share_of_inbound, "%")}</span>'
        + '<span>Touchless: <strong class="metric-missing">Niemierzone</strong></span></footer></article>'
        + '<article class="chart-panel response-panel"><header><div><span class="eyebrow">Odpowiedzi · 30 dni</span><h2>Pochodzenie</h2></div></header>'
        + _donut(response_classified, responses.sent, "sklasyfikowane", "teal")
        + response_breakdown
        + "<footer>Liczymy wyłącznie wysyłki powiązane z wiadomością źródłową.</footer></article>"
        + '<article class="chart-panel chart-wide"><header><div><span class="eyebrow">Bramka SMTP · 30 dni</span><h2>Próby dostarczenia</h2></div>'
        + f'<div class="chart-total"><strong>{delivery.accepted + delivery.failed}</strong><span>prób</span></div></header>'
        + _line_chart(
            delivery.daily,
            (("accepted", "Przyjęte", "teal"), ("failed", "Nieudane", "coral")),
            "Dzienne przyjęte i nieudane próby SMTP z ostatnich 30 dni",
        )
        + f'<footer><span>Przyjęcie {_metric(delivery_rate, "%")}</span><span>{delivery.bounced} rozpoznane odbicie</span></footer></article>'
        + "</section>"
        + '<section class="outreach-band">'
        + '<header class="outreach-head"><div><span class="eyebrow">Outreach · 90 dni</span><h2>Pozyskanie klientów</h2><p>Od wolumenu kampanii do realnej rejestracji.</p></div>'
        + f'<div class="outreach-rate">{_metric(outreach.reply_rate, "%")}<span>reply rate</span></div></header>'
        + '<div class="funnel-strip">'
        + _funnel_stage("Wysłane", outreach.sent)
        + _funnel_stage("Odpowiedzi", outreach.replied, outreach.sent)
        + _funnel_stage("Ludzkie", outreach.human_replies, outreach.replied)
        + _funnel_stage("Rejestracje", outreach.registrations, outreach.human_replies)
        + '</div><div class="outreach-grid">'
        + '<article class="chart-panel"><header><div><span class="eyebrow">Wolumen · 90 dni</span><h3>Aktywność wysyłki</h3></div>'
        + f'<div class="chart-total"><strong>{outreach.sent}</strong><span>wysłanych</span></div></header>'
        + _line_chart(
            outreach.daily,
            (("sent", "Wysłane dziennie", "blue"),),
            "Dzienny wolumen kampanii outreach z ostatnich 90 dni",
        )
        + '</article><article class="variant-panel"><header><span class="eyebrow">Eksperyment</span><h3>Warianty kampanii</h3><p>Reply rate względem najlepszego wariantu.</p></header>'
        + _variant_comparison(data)
        + "</article></div>"
        + '<p class="measurement-note">Konwersje kampanii pozostają nieprzypisane do wariantu; rejestracje pokazujemy osobno zamiast dopisywać sukces do kampanii.</p></section>'
    )


def _system_view(data: OperationalDashboard) -> str:
    overview = data.overview
    values = (
        ("Ostatni wpływ", _moment(overview.freshness.last_inbound_at)),
        ("Ostatnia próba wysyłki", _moment(overview.freshness.last_send_attempt_at)),
        (
            "Rejestr relacji",
            f"{overview.coverage.registered_clients} / {overview.coverage.companies}",
        ),
        ("Wygenerowano", _moment(overview.generated_at)),
    )
    rows = "".join(
        '<div class="system-row">'
        f"<span>{_esc(label)}</span><strong>{_esc(value)}</strong>"
        '<span class="status ok">Dostępne</span></div>'
        for label, value in values
    )
    return (
        _page_head(
            "Diagnostyka",
            "System",
            "Stan źródeł i świeżość projekcji operacyjnej.",
        )
        + '<section class="workspace-section">'
        + _section_head("Kontrola źródeł", "Dostępność", len(values))
        + f'<div class="system-list">{rows}</div></section>'
    )


def _navigation(active: WorkspaceView, data: OperationalDashboard, *, mobile: bool = False) -> str:
    counts = {
        "today": len(data.attention),
        "inbox": data.overview.approvals.pending,
        "cases": len(data.deadlines),
        "relationships": len(data.clients) + len(data.guests),
        "calendar": 0,
        "performance": 0,
        "system": 0,
    }
    labels = {
        "today": "Dzisiaj",
        "inbox": "Skrzynka",
        "cases": "Sprawy",
        "relationships": "Relacje",
        "calendar": "Kalendarz",
        "performance": "Wyniki",
        "system": "System",
    }
    views: tuple[WorkspaceView, ...] = (
        "today",
        "inbox",
        "cases",
        "relationships",
        "calendar",
        "performance",
        "system",
    )

    def link(view: WorkspaceView) -> str:
        count = f'<span class="nav-count">{counts[view]}</span>' if counts[view] else ""
        current = ' aria-current="page"' if active == view else ""
        return f'<a href="{_VIEW_PATHS[view]}"{current}><span>{labels[view]}</span>{count}</a>'

    if mobile:
        primary: tuple[WorkspaceView, ...] = ("today", "inbox", "cases", "performance")
        more: tuple[WorkspaceView, ...] = ("relationships", "calendar", "system")
        more_current = ' class="current"' if active in more else ""
        return (
            "".join(link(view) for view in primary)
            + '<details class="mobile-more">'
            + f"<summary{more_current}>Więcej</summary>"
            + '<div class="mobile-more-menu">'
            + "".join(link(view) for view in more)
            + "</div></details>"
        )
    return "".join(link(view) for view in views)


def _state(data: OperationalDashboard) -> tuple[str, str]:
    critical = sum(item.severity == "critical" for item in data.attention)
    if critical:
        return "critical", f"{critical} pilne"
    if data.attention:
        return "warning", f"{len(data.attention)} do uwagi"
    return "ok", "Spokojnie"


def render_dashboard(
    data: OperationalDashboard,
    principal: TailnetPrincipal,
    *,
    view: WorkspaceView = "today",
    degraded: bool = False,
    message_previews: Mapping[str, MessageContent] | None = None,
    action_tokens: Mapping[int, Mapping[str, str]] | None = None,
    reply_tokens: Mapping[str, str] | None = None,
    notice: str | None = None,
) -> str:
    tone, state_label = _state(data)
    login_label = principal.display_name or principal.login
    renderers = {
        "cases": _cases_view,
        "relationships": _relationships_view,
        "calendar": _calendar_view,
        "performance": _performance_view,
        "system": _system_view,
    }
    if view == "inbox":
        workspace_content = _inbox_view(
            data,
            message_previews or {},
            action_tokens or {},
            reply_tokens or {},
        )
    elif view == "today":
        workspace_content = _today_view(data, action_tokens or {})
    else:
        workspace_content = renderers[view](data)
    degraded_banner = ""
    if degraded:
        degraded_banner = (
            '<div class="degraded" role="status"><strong>Dane mogą być nieaktualne.</strong>'
            f" Pokazujemy ostatni poprawny stan z {_moment(data.overview.generated_at)}. "
            "System źródłowy jest chwilowo niedostępny.</div>"
        )
    notices = {
        "edited": ("ok", "Zmiany zapisane. Przeczytaj nową wersję przed wysłaniem."),
        "sent": ("ok", "Wiadomość została wysłana i zapisana w dzienniku."),
        "rejected": ("neutral", "Szkic został odrzucony. Nic nie wysłano."),
        "stale": ("warning", "Szkic zmienił się od otwarcia strony. Sprawdź aktualną wersję."),
        "failed": (
            "critical",
            "Operacja nie powiodła się. Wiadomość nie została uznana za wysłaną.",
        ),
        "reply_queued": ("ok", "Odpowiedź została zapisana w kolejce decyzji."),
        "reply_sent": ("ok", "Odpowiedź została wysłana i zachowała wątek wiadomości."),
        "reply_exists": ("warning", "Odpowiedź na tę wiadomość już istnieje."),
        "reply_blocked": (
            "warning",
            "Przyszła nowsza wiadomość od tego nadawcy. Przeczytaj ją przed wysłaniem.",
        ),
        "reply_mailbox_unknown": (
            "warning",
            "Nie udało się jednoznacznie ustalić skrzynki, z której należy odpowiedzieć.",
        ),
        "reply_unavailable": (
            "warning",
            "Na tę wiadomość nie można bezpiecznie odpowiedzieć z tablicy.",
        ),
        "reply_failed": (
            "critical",
            "Odpowiedź nie została uznana za wysłaną. Szkic pozostaje w kolejce.",
        ),
    }
    notice_banner = ""
    if notice in notices:
        notice_tone, notice_text = notices[notice]
        notice_banner = (
            f'<div class="action-notice {notice_tone}" role="status">{_esc(notice_text)}</div>'
        )
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Sekretariat · {_esc(_VIEW_TITLES[view])}</title>
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
  <header class="appbar">
    <div class="brand"><span class="brand-mark">K</span><strong>Sekretariat</strong></div>
    <div class="app-state"><span class="signal {tone}"></span><strong>{_esc(state_label)}</strong></div>
    <div class="identity">{_esc(login_label)}</div>
    <a class="icon-button" href="{_VIEW_PATHS[view]}" aria-label="Odśwież" title="Odśwież">↻</a>
  </header>
  <nav class="mobile-nav" aria-label="Nawigacja mobilna">{_navigation(view, data, mobile=True)}</nav>
  <div class="app-layout">
    <aside class="sidebar">
      <nav aria-label="Główna nawigacja">{_navigation(view, data)}</nav>
      <div class="sidebar-foot"><span class="signal ok"></span><span>Połączenie prywatne</span></div>
    </aside>
    <main class="workspace">{degraded_banner}{notice_banner}{workspace_content}</main>
  </div>
</body>
</html>"""


def render_message(content: MessageContent, principal: TailnetPrincipal) -> str:
    login_label = principal.display_name or principal.login
    if content.available:
        headers = (
            ("Od", content.from_address),
            ("Do", content.to_address),
            ("Skrzynka", content.mailbox),
            ("Folder", content.folder),
            ("Data", content.sent_at),
        )
        header_rows = "".join(
            f"<div><span>{_esc(label)}</span><strong>{_esc(value or 'brak danych')}</strong></div>"
            for label, value in headers
        )
        attachment_rows = "".join(
            '<div class="attachment-row">'
            f'<div class="company-token">{_esc(item.filename.rsplit(".", 1)[-1].upper()[:3])}</div>'
            f"<div><strong>{_esc(item.filename)}</strong><span>{_esc(item.content_type)} · {item.size_bytes / 1024:.1f} KB</span></div>"
            "</div>"
            for item in content.attachments
        ) or _empty("Wiadomość nie zawiera załączników.")
        body = f'<pre class="message-body">{_esc(content.body_text or "(brak treści tekstowej)")}</pre>'
        inner = (
            '<a class="back-link" href="/inbox">← Skrzynka</a>'
            f'<header class="message-head"><span class="eyebrow">Treść źródłowa</span><h1>{_esc(content.subject or "(bez tematu)")}</h1></header>'
            f'<div class="message-headers">{header_rows}</div>'
            '<section class="message-section"><span class="eyebrow">Wiadomość</span>'
            f"{body}</section>"
            '<section class="message-section"><span class="eyebrow">Załączniki</span>'
            f'<div class="attachment-list">{attachment_rows}</div></section>'
        )
    else:
        inner = (
            '<a class="back-link" href="/inbox">← Skrzynka</a>'
            '<div class="message-unavailable"><strong>Treść nie została jeszcze zarchiwizowana.</strong>'
            "<p>Rejestr wpływu istnieje, ale prywatny cache nie zawiera jeszcze tej wiadomości.</p></div>"
        )
    return f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Sekretariat · {_esc(content.subject or "Treść wiadomości")}</title>
  <link rel="stylesheet" href="/assets/app.css">
</head>
<body>
  <header class="appbar">
    <div class="brand"><span class="brand-mark">K</span><strong>Sekretariat</strong></div>
    <div class="app-state"><span class="signal ok"></span><strong>Podgląd prywatny</strong></div>
    <div class="identity">{_esc(login_label)}</div>
  </header>
  <main class="message-workspace">{inner}</main>
</body>
</html>"""
