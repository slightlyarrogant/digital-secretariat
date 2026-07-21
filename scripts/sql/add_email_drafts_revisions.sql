-- Additive audit trail for draft edits.
-- mail_rail.edit_draft appends the OLD version before overwriting body/subject,
-- so the board and the approver can always see what changed. Append-only.
-- Idempotent; applied operationally (alembic chain broken — see 075_add_client_registry.py).

ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS revisions JSONB NOT NULL DEFAULT '[]'::jsonb;
COMMENT ON COLUMN email_drafts.revisions IS
    'Audyt edycji draftu: [{at, via, old_subject, old_body}] — append-only przez mail_rail.edit_draft';
