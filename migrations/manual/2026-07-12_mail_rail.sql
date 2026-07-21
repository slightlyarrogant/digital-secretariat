-- Reference mail-rail schema.
-- Idempotent DDL (Alembic chain is broken — apply via psql):
--   psql "$DATABASE_URL" \
--     --dbname="$DATABASE_URL" -f migrations/manual/2026-07-12_mail_rail.sql
--
-- Tables:
--   email_drafts      — curated queue (pending_approval -> approved -> sent |
--                       rejected | expired | failed), released by WhatsApp reply
--   mail_rail_sends   — atomic idempotency guard for send_template
--                       (unique (template, COALESCE(company_id,-1), idem_key);
--                       expression index because PG14 treats NULL company_id as
--                       always-distinct in a plain UNIQUE constraint, which
--                       would disable the guard for company-less sends.
--                       Row deleted on failed/skipped send so retry stays
--                       possible)
--   mail_rail_optouts — generalized kill-switch: per company_id + category,
--                       category '*' = all rail mail for that company.
--                       (Generalizes the obligation-specific
--                       companies.connector_auto_questions boolean.)

CREATE TABLE IF NOT EXISTS email_drafts (
  id SERIAL PRIMARY KEY,
  company_id INT NULL,
  from_address TEXT NOT NULL,
  to_address TEXT NOT NULL,
  cc_addresses JSONB,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  attachments JSONB,
  log_category TEXT NOT NULL DEFAULT 'curated',
  status TEXT NOT NULL DEFAULT 'pending_approval',
  due_at TIMESTAMPTZ,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ,
  decision_via TEXT,
  sent_log_id INT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_drafts_status ON email_drafts(status);

CREATE TABLE IF NOT EXISTS mail_rail_sends (
  id SERIAL PRIMARY KEY,
  template TEXT NOT NULL,
  company_id INT,
  idem_key TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  send_log_id INT
);

-- NULL-safe uniqueness (see header). ON CONFLICT in mail_rail.py targets this
-- exact expression list.
ALTER TABLE mail_rail_sends
  DROP CONSTRAINT IF EXISTS mail_rail_sends_template_company_id_idem_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mail_rail_sends_idem
  ON mail_rail_sends (template, COALESCE(company_id, -1), idem_key);

CREATE TABLE IF NOT EXISTS mail_rail_optouts (
  id SERIAL PRIMARY KEY,
  company_id INT NOT NULL,
  category TEXT NOT NULL DEFAULT '*',
  reason TEXT,
  created_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(company_id, category)
);

-- Statuses (email_drafts.status):
--   pending_approval | approved | sent | rejected | expired | failed
