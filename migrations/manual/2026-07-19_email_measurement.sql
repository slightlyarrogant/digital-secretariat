-- Evidence fields for measuring outbound automation without inferring it from sent_by.
-- Safe for existing senders: new columns are nullable and existing INSERT lists remain valid.

BEGIN;

ALTER TABLE email_send_log
    ADD COLUMN IF NOT EXISTS automation_mode VARCHAR(40),
    ADD COLUMN IF NOT EXISTS template_key VARCHAR(100),
    ADD COLUMN IF NOT EXISTS template_version VARCHAR(64);

DO $constraint$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_email_send_log_automation_mode'
    ) THEN
        ALTER TABLE email_send_log
            ADD CONSTRAINT ck_email_send_log_automation_mode
            CHECK (
                automation_mode IS NULL OR automation_mode IN (
                    'automatic_template', 'automatic_ai', 'formatted_approved', 'human'
                )
            );
    END IF;
END
$constraint$;

UPDATE email_send_log
SET automation_mode = CASE
        WHEN sent_by LIKE 'mail_rail:curated:%' THEN 'formatted_approved'
        WHEN sent_by LIKE 'mail_rail:%' THEN 'automatic_template'
        ELSE automation_mode
    END,
    template_key = CASE
        WHEN sent_by LIKE 'mail_rail:%' AND sent_by NOT LIKE 'mail_rail:curated:%'
        THEN substring(sent_by FROM length('mail_rail:') + 1)
        ELSE template_key
    END
WHERE automation_mode IS NULL AND sent_by LIKE 'mail_rail:%';

CREATE INDEX IF NOT EXISTS idx_email_send_log_automation_mode
    ON email_send_log (automation_mode, sent_at DESC);

COMMENT ON COLUMN email_send_log.automation_mode IS
    'Provenance: automatic_template, automatic_ai, formatted_approved, human; NULL means unclassified.';
COMMENT ON COLUMN email_send_log.template_key IS
    'Stable template identifier when automation_mode uses a formatted template.';
COMMENT ON COLUMN email_send_log.template_version IS
    'Immutable template version or content hash used for the send.';

COMMIT;
