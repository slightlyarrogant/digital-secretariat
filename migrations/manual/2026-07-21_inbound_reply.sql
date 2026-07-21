-- Additive schema for an audited reply to an inbound message.
-- Zawiera też retro-dokumentację kolumny body_html (dodanej ręcznie 21.07 rano, drafty #21-#24).
-- Wykonanie NA PRODUKCJI wymaga osobnej zgody właściciela (DoD kontraktu).

-- ═══ UPGRADE ═══
ALTER TABLE email_processing_registry ADD COLUMN IF NOT EXISTS recipient_address VARCHAR(255);
COMMENT ON COLUMN email_processing_registry.recipient_address IS
  'Adres skrzynki, na której fizycznie odebrano mail (system_email_accounts.email_address). Źródło From dla odpowiedzi.';

ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS body_html TEXT;
ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS source_registry_id UUID;
ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS in_reply_to VARCHAR(500);
ALTER TABLE email_drafts ADD COLUMN IF NOT EXISTS references_header TEXT;

CREATE INDEX IF NOT EXISTS idx_email_drafts_source_registry
  ON email_drafts (source_registry_id) WHERE source_registry_id IS NOT NULL;

-- Guard: najwyżej JEDNA aktywna odpowiedź na jeden wpływ (rejected/expired zwalniają slot)
CREATE UNIQUE INDEX IF NOT EXISTS uq_email_drafts_active_reply_per_source
  ON email_drafts (source_registry_id)
  WHERE source_registry_id IS NOT NULL
    AND status IN ('pending_approval', 'approved', 'sent', 'failed');

-- ═══ DOWNGRADE ═══
-- DROP INDEX IF EXISTS uq_email_drafts_active_reply_per_source;
-- DROP INDEX IF EXISTS idx_email_drafts_source_registry;
-- ALTER TABLE email_drafts DROP COLUMN IF EXISTS references_header;
-- ALTER TABLE email_drafts DROP COLUMN IF EXISTS in_reply_to;
-- ALTER TABLE email_drafts DROP COLUMN IF EXISTS source_registry_id;
-- ALTER TABLE email_drafts DROP COLUMN IF EXISTS body_html;
-- ALTER TABLE email_processing_registry DROP COLUMN IF EXISTS recipient_address;
