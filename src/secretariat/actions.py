"""Narrow action boundary between the owner board and the canonical mail rail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DraftActionConflict(Exception):
    """The draft changed or was decided after the owner loaded the page."""


class DraftActionError(Exception):
    """The canonical rail could not complete the requested action."""


class ReplyActionError(Exception):
    """A reply could not be created or released through the canonical rail."""

    def __init__(self, code: str, *, draft_id: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.draft_id = draft_id


class ReplyActionConflict(ReplyActionError):
    """Another reply already exists for this inbound message."""


@dataclass(frozen=True)
class ReplyActionResult:
    draft_id: int
    status: str
    reason: str | None = None


class DraftActions(Protocol):
    def edit(
        self,
        draft_id: int,
        *,
        subject: str,
        body: str,
        expected_revision: int,
        via: str,
    ) -> None: ...

    def approve(self, draft_id: int, *, expected_revision: int, via: str) -> None: ...

    def reject(self, draft_id: int, *, expected_revision: int, via: str) -> None: ...


class ReplyActions(Protocol):
    def create(
        self,
        registry_id: str,
        *,
        subject: str,
        body: str,
        created_by: str,
    ) -> ReplyActionResult: ...

    def release(
        self,
        draft_id: int,
        *,
        expected_revision: int,
        via: str,
    ) -> ReplyActionResult: ...


class MailRailDraftActions:
    """Adapt UI commands to the single audited mail-rail implementation."""

    @staticmethod
    def _raise_for_result(result: dict) -> None:
        status = result.get("status")
        if status in {"pending_approval", "sent", "rejected"}:
            return
        detail = str(result.get("detail") or "mail rail action failed")
        if result.get("reason") == "stale_revision":
            raise DraftActionConflict(detail)
        raise DraftActionError(detail)

    def edit(
        self,
        draft_id: int,
        *,
        subject: str,
        body: str,
        expected_revision: int,
        via: str,
    ) -> None:
        from src.services import mail_rail

        self._raise_for_result(
            mail_rail.edit_draft(
                draft_id,
                subject=subject,
                body=body,
                expected_revision=expected_revision,
                via=via,
            )
        )

    def approve(self, draft_id: int, *, expected_revision: int, via: str) -> None:
        from src.services import mail_rail

        self._raise_for_result(
            mail_rail.release_draft(
                draft_id,
                via=via,
                expected_revision=expected_revision,
            )
        )

    def reject(self, draft_id: int, *, expected_revision: int, via: str) -> None:
        from src.services import mail_rail

        self._raise_for_result(
            mail_rail.reject_draft(
                draft_id,
                via=via,
                expected_revision=expected_revision,
            )
        )


class MailRailReplyActions:
    """Adapt inline owner replies to reply-draft and release rail verbs."""

    @staticmethod
    def _result(value: dict) -> ReplyActionResult:
        draft_id = value.get("draft_id")
        status = str(value.get("status") or "error")
        if not isinstance(draft_id, int):
            raise ReplyActionError("invalid_rail_result")
        return ReplyActionResult(
            draft_id=draft_id,
            status=status,
            reason=str(value.get("reason")) if value.get("reason") else None,
        )

    def create(
        self,
        registry_id: str,
        *,
        subject: str,
        body: str,
        created_by: str,
    ) -> ReplyActionResult:
        from src.services import mail_rail

        try:
            result = mail_rail.create_reply_draft(
                registry_id,
                body,
                subject=subject,
                created_by=created_by,
            )
        except mail_rail.MailRailError as exc:
            error_type = (
                ReplyActionConflict if exc.code == "reply_already_exists" else ReplyActionError
            )
            raise error_type(exc.code, draft_id=exc.draft_id) from exc
        return self._result(result)

    def release(
        self,
        draft_id: int,
        *,
        expected_revision: int,
        via: str,
    ) -> ReplyActionResult:
        from src.services import mail_rail

        result = mail_rail.release_draft(
            draft_id,
            via=via,
            expected_revision=expected_revision,
        )
        if result.get("reason") == "stale_revision":
            raise ReplyActionConflict("stale_revision", draft_id=draft_id)
        return self._result(result)
