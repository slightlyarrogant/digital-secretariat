"""Standalone, tailnet-only FastAPI application for the Digital Secretariat."""

import hashlib
import hmac
import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeVar
from urllib.parse import parse_qs, urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response as StarletteResponse

from src.secretariat.actions import (
    DraftActionConflict,
    DraftActionError,
    DraftActions,
    MailRailDraftActions,
    MailRailReplyActions,
    ReplyActionConflict,
    ReplyActionError,
    ReplyActions,
)
from src.secretariat.auth import TailnetPrincipal, require_tailnet_principal
from src.secretariat.dashboard import DashboardRepository, PostgresDashboardRepository
from src.secretariat.database import SecretariatDatabaseError, create_session
from src.secretariat.mail_content import read_cached_message
from src.secretariat.schemas import (
    LiveStatus,
    MessageContent,
    OperationalDashboard,
    OperationalOverview,
    ReadyStatus,
)
from src.secretariat.web import WorkspaceView, render_dashboard, render_message

SERVICE_VERSION = "0.1.0"
logger = logging.getLogger("digital_secretariat")
_MAX_FORM_BYTES = 525_000
_FormModel = TypeVar("_FormModel", bound=BaseModel)

_WORKSPACE_VIEWS: dict[str, WorkspaceView] = {
    "/": "today",
    "/inbox": "inbox",
    "/cases": "cases",
    "/relationships": "relationships",
    "/calendar": "calendar",
    "/performance": "performance",
    "/system": "system",
}


class _DecisionForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    action_token: str = Field(min_length=64, max_length=64)


class _EditDraftForm(_DecisionForm):
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=500_000)


class _ReplyForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=10_000)
    intent: Literal["queue", "send"]
    action_token: str = Field(min_length=64, max_length=64)


async def _read_urlencoded_form(request: Request, model: type[_FormModel]) -> _FormModel:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_FORM_BYTES:
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST) from exc
    raw = await request.body()
    if len(raw) > _MAX_FORM_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    try:
        values = {
            key: entries[-1]
            for key, entries in parse_qs(
                raw.decode("utf-8"),
                keep_blank_values=True,
                max_num_fields=8,
            ).items()
        }
        return model.model_validate(values)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from exc


def _session_factory() -> Session:
    return create_session()


def _get_repository(request: Request) -> DashboardRepository:
    repository: DashboardRepository = request.app.state.overview_repository
    return repository


def _get_draft_actions(request: Request) -> DraftActions:
    actions: DraftActions | None = request.app.state.draft_actions
    if actions is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return actions


def _get_reply_actions(request: Request) -> ReplyActions:
    actions: ReplyActions | None = request.app.state.reply_actions
    if actions is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return actions


def _action_payload(
    principal: TailnetPrincipal, draft_id: int, revision: int, action: str
) -> bytes:
    return f"{principal.login}\0{draft_id}\0{revision}\0{action}".encode()


def _action_token(
    secret: bytes,
    principal: TailnetPrincipal,
    draft_id: int,
    revision: int,
    action: str,
) -> str:
    return hmac.new(
        secret,
        _action_payload(principal, draft_id, revision, action),
        hashlib.sha256,
    ).hexdigest()


def _message_fingerprint(content: MessageContent) -> str:
    fields = (
        content.registry_id,
        content.from_address or "",
        content.to_address or "",
        content.sent_at or "",
        content.subject or "",
    )
    return hashlib.sha256("\0".join(fields).encode()).hexdigest()


def _reply_action_token(
    secret: bytes,
    principal: TailnetPrincipal,
    content: MessageContent,
) -> str:
    payload = (
        f"{principal.login}\0reply\0{content.registry_id}\0{_message_fingerprint(content)}"
    ).encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _canonical_hostname(value: str | None) -> str | None:
    if not value:
        return None
    return value.casefold().rstrip(".") or None


def _origin_matches_request_host(origin: str, host_header: str) -> bool:
    try:
        parsed_origin = urlsplit(origin)
        parsed_host = urlsplit(f"//{host_header}")
        origin_port = parsed_origin.port
        host_port = parsed_host.port
    except ValueError:
        return False

    if parsed_origin.scheme not in {"http", "https"}:
        return False
    if (
        parsed_origin.username is not None
        or parsed_origin.password is not None
        or parsed_origin.path not in {"", "/"}
        or parsed_origin.query
        or parsed_origin.fragment
        or parsed_host.username is not None
        or parsed_host.password is not None
        or parsed_host.path
        or parsed_host.query
        or parsed_host.fragment
    ):
        return False
    if _canonical_hostname(parsed_origin.hostname) != _canonical_hostname(parsed_host.hostname):
        return False

    default_origin_port = 443 if parsed_origin.scheme == "https" else 80
    effective_origin_port = origin_port or default_origin_port
    if host_port is None:
        return origin_port is None or origin_port == default_origin_port
    return host_port == effective_origin_port


def _require_action_origin(request: Request, *, context: dict[str, object]) -> None:
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site and fetch_site.casefold() != "same-origin":
        logger.warning(
            "Secretariat action rejected at browser-site boundary",
            extra={**context, "fetch_site": fetch_site},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    null_origin_without_same_site = origin == "null" and (
        not fetch_site or fetch_site.casefold() != "same-origin"
    )
    mismatched_named_origin = (
        origin is not None
        and bool(origin)
        and origin != "null"
        and not _origin_matches_request_host(origin, request.headers.get("host", ""))
    )
    if null_origin_without_same_site or mismatched_named_origin:
        logger.warning(
            "Secretariat action rejected at origin boundary",
            extra={
                **context,
                "origin": origin,
                "request_host": request.headers.get("host", ""),
            },
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def _require_action_token(
    request: Request,
    principal: TailnetPrincipal,
    draft_id: int,
    revision: int,
    action: str,
    submitted: str,
) -> None:
    context: dict[str, object] = {"draft_id": draft_id, "action": action}
    _require_action_origin(request, context=context)
    expected = _action_token(
        request.app.state.action_secret,
        principal,
        draft_id,
        revision,
        action,
    )
    if not hmac.compare_digest(expected, submitted):
        logger.warning(
            "Secretariat action rejected at signed-token boundary",
            extra={**context, "revision": revision},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def _require_reply_action_token(
    request: Request,
    principal: TailnetPrincipal,
    content: MessageContent,
    submitted: str,
) -> None:
    context: dict[str, object] = {
        "registry_id": content.registry_id,
        "action": "reply",
    }
    _require_action_origin(request, context=context)
    expected = _reply_action_token(
        request.app.state.action_secret,
        principal,
        content,
    )
    if not hmac.compare_digest(expected, submitted):
        logger.warning(
            "Secretariat reply rejected at signed-token boundary",
            extra=context,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def _load_action_secret() -> bytes:
    path_value = os.getenv("SECRETARIAT_ACTION_SECRET_FILE", "").strip()
    if not path_value:
        return secrets.token_bytes(32)
    try:
        secret = Path(path_value).read_bytes().strip()
    except OSError as exc:
        raise RuntimeError("Secretariat action-token credential is unreadable") from exc
    if len(secret) < 32:
        raise RuntimeError("Secretariat action-token credential is too short")
    return secret


def _snapshot_path() -> Path | None:
    value = os.getenv("SECRETARIAT_SNAPSHOT_FILE", "").strip()
    return Path(value) if value else None


def _remember_dashboard(control_plane: FastAPI, data: OperationalDashboard) -> None:
    control_plane.state.last_dashboard = data
    path = _snapshot_path()
    if path is None:
        return
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    try:
        temporary.write_text(data.model_dump_json(), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    except OSError:
        logger.exception("Secretariat dashboard snapshot write failed")
        temporary.unlink(missing_ok=True)


def _last_dashboard(control_plane: FastAPI) -> OperationalDashboard | None:
    cached: OperationalDashboard | None = control_plane.state.last_dashboard
    if cached is not None:
        return cached
    path = _snapshot_path()
    if path is None:
        return None
    try:
        cached = OperationalDashboard.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("Secretariat dashboard snapshot read failed")
        return None
    control_plane.state.last_dashboard = cached
    return cached


def create_app(
    repository: DashboardRepository | None = None,
    message_reader: Callable[[str], MessageContent] | None = None,
    draft_actions: DraftActions | None = None,
    reply_actions: ReplyActions | None = None,
) -> FastAPI:
    control_plane = FastAPI(
        title="Digital Secretariat Control Plane",
        version=SERVICE_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    control_plane.state.overview_repository = repository or PostgresDashboardRepository(
        _session_factory
    )
    control_plane.state.last_dashboard = None
    control_plane.state.message_reader = message_reader or read_cached_message
    actions_enabled = os.getenv("SECRETARIAT_DRAFT_ACTIONS_ENABLED", "").casefold() == "true"
    if draft_actions is not None:
        control_plane.state.draft_actions = draft_actions
    elif actions_enabled:
        control_plane.state.draft_actions = MailRailDraftActions()
    else:
        control_plane.state.draft_actions = None
    replies_enabled = os.getenv("SECRETARIAT_REPLY_ACTIONS_ENABLED", "").casefold() == "true"
    if reply_actions is not None:
        control_plane.state.reply_actions = reply_actions
    elif replies_enabled:
        control_plane.state.reply_actions = MailRailReplyActions()
    else:
        control_plane.state.reply_actions = None
    control_plane.state.action_secret = _load_action_secret()
    control_plane.mount(
        "/assets",
        StaticFiles(directory=Path(__file__).with_name("static")),
        name="secretariat-assets",
    )

    def inbox_previews(data: OperationalDashboard) -> dict[str, MessageContent]:
        reader: Callable[[str], MessageContent] = control_plane.state.message_reader
        previews: dict[str, MessageContent] = {}
        for item in data.inbound:
            try:
                previews[item.id] = reader(item.id)
            except (OSError, ValueError):
                logger.exception("Secretariat inline message preview failed", extra={"id": item.id})
                previews[item.id] = MessageContent(registry_id=item.id, available=False)
        return previews

    @control_plane.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[StarletteResponse]],
    ) -> StarletteResponse:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        return response

    @control_plane.get("/health/live", response_model=LiveStatus)
    def live() -> LiveStatus:
        return LiveStatus(version=SERVICE_VERSION)

    @control_plane.get("/health/ready", response_model=ReadyStatus)
    def ready(
        response: Response,
        repo: DashboardRepository = Depends(_get_repository),
    ) -> ReadyStatus:
        try:
            missing = repo.missing_relations()
            if not missing:
                repo.read_dashboard(datetime.now(UTC))
        except (SQLAlchemyError, SecretariatDatabaseError):
            logger.exception("Secretariat readiness database check failed")
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadyStatus(status="not_ready")
        if missing:
            logger.warning("Secretariat readiness missing relations: %s", ", ".join(missing))
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadyStatus(status="not_ready")
        return ReadyStatus(status="ready")

    @control_plane.get("/api/v1/overview", response_model=OperationalOverview)
    def overview(
        _principal: TailnetPrincipal = Depends(require_tailnet_principal),
        repo: DashboardRepository = Depends(_get_repository),
    ) -> OperationalOverview:
        try:
            return repo.read(datetime.now(UTC))
        except (SQLAlchemyError, SecretariatDatabaseError) as exc:
            logger.exception("Secretariat overview query failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Operational projection is unavailable",
            ) from exc

    @control_plane.get("/api/v1/dashboard", response_model=OperationalDashboard)
    def dashboard_api(
        _principal: TailnetPrincipal = Depends(require_tailnet_principal),
        repo: DashboardRepository = Depends(_get_repository),
    ) -> OperationalDashboard:
        try:
            return repo.read_dashboard(datetime.now(UTC))
        except (SQLAlchemyError, SecretariatDatabaseError) as exc:
            logger.exception("Secretariat dashboard query failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Operational dashboard is unavailable",
            ) from exc

    @control_plane.get("/api/v1/inbox/{registry_id}", response_model=MessageContent)
    def message_api(
        registry_id: str,
        _principal: TailnetPrincipal = Depends(require_tailnet_principal),
    ) -> MessageContent:
        reader: Callable[[str], MessageContent] = control_plane.state.message_reader
        return reader(registry_id)

    @control_plane.get("/inbox/{registry_id}", response_class=HTMLResponse)
    def message_page(
        registry_id: str,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
    ) -> HTMLResponse:
        reader: Callable[[str], MessageContent] = control_plane.state.message_reader
        return HTMLResponse(render_message(reader(registry_id), principal))

    def action_redirect(notice: str, *, draft_id: int | None = None) -> RedirectResponse:
        fragment = f"#draft-{draft_id}" if draft_id is not None else ""
        return RedirectResponse(
            url=f"/inbox?notice={notice}{fragment}", status_code=status.HTTP_303_SEE_OTHER
        )

    @control_plane.post("/inbox/{registry_id}/reply")
    async def reply_to_inbound(
        request: Request,
        registry_id: str,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
        actions: ReplyActions = Depends(_get_reply_actions),
    ) -> RedirectResponse:
        form = await _read_urlencoded_form(request, _ReplyForm)
        reader: Callable[[str], MessageContent] = control_plane.state.message_reader
        content = reader(registry_id)
        if not content.available or content.registry_id != registry_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT)
        _require_reply_action_token(
            request,
            principal,
            content,
            form.action_token,
        )
        subject = form.subject.strip()
        body = form.body.strip()
        if not subject or not body:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        try:
            created = await run_in_threadpool(
                actions.create,
                registry_id,
                subject=subject,
                body=body,
                created_by=f"secretariat-board:{principal.login}",
            )
        except ReplyActionConflict as exc:
            return action_redirect("reply_exists", draft_id=exc.draft_id)
        except ReplyActionError as exc:
            notice = {
                "source_mailbox_unknown": "reply_mailbox_unknown",
                "source_mailbox_unavailable": "reply_mailbox_unknown",
                "invalid_sender": "reply_unavailable",
            }.get(exc.code, "reply_failed")
            return action_redirect(notice, draft_id=exc.draft_id)

        if form.intent == "queue":
            return action_redirect("reply_queued", draft_id=created.draft_id)

        try:
            released = await run_in_threadpool(
                actions.release,
                created.draft_id,
                expected_revision=0,
                via=f"secretariat-board:{principal.login}",
            )
        except ReplyActionConflict as exc:
            return action_redirect("reply_exists", draft_id=exc.draft_id)
        except ReplyActionError as exc:
            return action_redirect("reply_failed", draft_id=exc.draft_id or created.draft_id)

        notice = {
            "sent": "reply_sent",
            "blocked": "reply_blocked",
            "failed": "reply_failed",
        }.get(released.status, "reply_failed")
        return action_redirect(notice, draft_id=released.draft_id)

    @control_plane.post("/drafts/{draft_id}/edit")
    async def edit_draft(
        request: Request,
        draft_id: int,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
        actions: DraftActions = Depends(_get_draft_actions),
    ) -> RedirectResponse:
        form = await _read_urlencoded_form(request, _EditDraftForm)
        _require_action_token(
            request,
            principal,
            draft_id,
            form.expected_revision,
            "edit",
            form.action_token,
        )
        subject = form.subject.strip()
        body = form.body.strip()
        if not subject or not body:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
        try:
            await run_in_threadpool(
                actions.edit,
                draft_id,
                subject=subject.strip(),
                body=body.strip(),
                expected_revision=form.expected_revision,
                via=f"secretariat-board:{principal.login}",
            )
        except DraftActionConflict:
            return action_redirect("stale")
        except DraftActionError:
            logger.exception("Secretariat draft edit failed", extra={"draft_id": draft_id})
            return action_redirect("failed")
        return action_redirect("edited")

    @control_plane.post("/drafts/{draft_id}/approve")
    async def approve_draft(
        request: Request,
        draft_id: int,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
        actions: DraftActions = Depends(_get_draft_actions),
    ) -> RedirectResponse:
        form = await _read_urlencoded_form(request, _DecisionForm)
        _require_action_token(
            request,
            principal,
            draft_id,
            form.expected_revision,
            "approve",
            form.action_token,
        )
        try:
            await run_in_threadpool(
                actions.approve,
                draft_id,
                expected_revision=form.expected_revision,
                via=f"secretariat-board:{principal.login}",
            )
        except DraftActionConflict:
            return action_redirect("stale")
        except DraftActionError:
            logger.exception("Secretariat draft approval failed", extra={"draft_id": draft_id})
            return action_redirect("failed")
        return action_redirect("sent")

    @control_plane.post("/drafts/{draft_id}/reject")
    async def reject_draft(
        request: Request,
        draft_id: int,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
        actions: DraftActions = Depends(_get_draft_actions),
    ) -> RedirectResponse:
        form = await _read_urlencoded_form(request, _DecisionForm)
        _require_action_token(
            request,
            principal,
            draft_id,
            form.expected_revision,
            "reject",
            form.action_token,
        )
        try:
            await run_in_threadpool(
                actions.reject,
                draft_id,
                expected_revision=form.expected_revision,
                via=f"secretariat-board:{principal.login}",
            )
        except DraftActionConflict:
            return action_redirect("stale")
        except DraftActionError:
            logger.exception("Secretariat draft rejection failed", extra={"draft_id": draft_id})
            return action_redirect("failed")
        return action_redirect("rejected")

    @control_plane.get("/", response_class=HTMLResponse)
    @control_plane.get("/inbox", response_class=HTMLResponse)
    @control_plane.get("/cases", response_class=HTMLResponse)
    @control_plane.get("/relationships", response_class=HTMLResponse)
    @control_plane.get("/calendar", response_class=HTMLResponse)
    @control_plane.get("/performance", response_class=HTMLResponse)
    @control_plane.get("/system", response_class=HTMLResponse)
    def dashboard_page(
        request: Request,
        principal: TailnetPrincipal = Depends(require_tailnet_principal),
        repo: DashboardRepository = Depends(_get_repository),
    ) -> HTMLResponse:
        view = _WORKSPACE_VIEWS[request.url.path]
        try:
            data = repo.read_dashboard(datetime.now(UTC))
            _remember_dashboard(control_plane, data)
        except (SQLAlchemyError, SecretariatDatabaseError) as exc:
            logger.exception("Secretariat dashboard page query failed")
            cached = _last_dashboard(control_plane)
            if cached is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Operational dashboard is unavailable",
                ) from exc
            previews = inbox_previews(cached) if view == "inbox" else None
            response = HTMLResponse(
                render_dashboard(
                    cached,
                    principal,
                    view=view,
                    degraded=True,
                    message_previews=previews,
                    notice=request.query_params.get("notice"),
                )
            )
            response.headers["Warning"] = '110 - "Response is stale"'
            response.headers["X-Secretariat-Data-State"] = "stale"
            return response
        previews = inbox_previews(data) if view == "inbox" else None
        action_tokens: dict[int, dict[str, str]] = {}
        reply_tokens: dict[str, str] = {}
        # Tokeny akcji dla KAŻDEGO widoku (nie tylko /inbox) — kolejka decyzji
        # ma być obsługiwalna ze strony "Dzisiaj" (product rule).
        if control_plane.state.draft_actions is not None:
            for draft in data.approvals:
                action_tokens[draft.id] = {
                    action: _action_token(
                        control_plane.state.action_secret,
                        principal,
                        draft.id,
                        draft.revision_count,
                        action,
                    )
                    for action in ("edit", "approve", "reject")
                }
        if control_plane.state.reply_actions is not None and previews is not None:
            for registry_id, content in previews.items():
                if content.available:
                    reply_tokens[registry_id] = _reply_action_token(
                        control_plane.state.action_secret,
                        principal,
                        content,
                    )
        return HTMLResponse(
            render_dashboard(
                data,
                principal,
                view=view,
                message_previews=previews,
                action_tokens=action_tokens,
                reply_tokens=reply_tokens,
                notice=request.query_params.get("notice"),
            )
        )

    return control_plane


app = create_app()
