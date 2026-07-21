\set ON_ERROR_STOP on

BEGIN;

DO $policy$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'secretariat_reader') THEN
        RAISE EXCEPTION 'Required role secretariat_reader does not exist';
    END IF;
END
$policy$;

CREATE TEMP TABLE secretariat_reader_allowed_columns (
    table_name text NOT NULL,
    column_name text NOT NULL,
    PRIMARY KEY (table_name, column_name)
) ON COMMIT DROP;

INSERT INTO secretariat_reader_allowed_columns (table_name, column_name)
VALUES
    ('companies', 'id'),
    ('companies', 'short_name'),
    ('companies', 'name'),
    ('companies', 'nip'),
    ('client_registry', 'id'),
    ('user_companies', 'user_id'),
    ('user_companies', 'company_id'),
    ('user_companies', 'is_active'),
    ('client_registry_v', 'company_id'),
    ('client_registry_v', 'effective_status'),
    ('client_registry_v', 'owner'),
    ('client_registry_v', 'service_scope'),
    ('client_registry_v', 'contract_ok'),
    ('client_registry_v', 'vat_whitelist_status'),
    ('client_registry_v', 'ksef_token_present'),
    ('client_registry_v', 'mismatch_vat'),
    ('client_registry_v', 'mismatch_status'),
    ('email_processing_registry', 'id'),
    ('email_processing_registry', 'received_at'),
    ('email_processing_registry', 'created_at'),
    ('email_processing_registry', 'company_id'),
    ('email_processing_registry', 'processing_status'),
    ('email_processing_registry', 'email_type'),
    ('email_processing_registry', 'sender_email'),
    ('email_processing_registry', 'subject'),
    ('client_obligations', 'id'),
    ('client_obligations', 'company_id'),
    ('client_obligations', 'title'),
    ('client_obligations', 'owner'),
    ('client_obligations', 'status'),
    ('client_obligations', 'due_date'),
    ('client_obligations', 'state'),
    ('client_obligations', 'category'),
    ('email_drafts', 'id'),
    ('email_drafts', 'company_id'),
    ('email_drafts', 'to_address'),
    ('email_drafts', 'subject'),
    ('email_drafts', 'body'),
    ('email_drafts', 'revisions'),
    ('email_drafts', 'status'),
    ('email_drafts', 'due_at'),
    ('email_drafts', 'created_at'),
    ('email_drafts', 'sent_log_id'),
    ('email_drafts', 'error'),
    ('email_send_log', 'id'),
    ('email_send_log', 'sent_at'),
    ('email_send_log', 'success'),
    ('email_send_log', 'in_reply_to'),
    ('email_send_log', 'error_message'),
    ('email_send_log', 'automation_mode'),
    ('guest_register', 'id'),
    ('guest_register', 'display_name'),
    ('guest_register', 'email'),
    ('guest_register', 'stage'),
    ('guest_register', 'next_action'),
    ('guest_register', 'next_action_owner'),
    ('guest_register', 'next_action_due'),
    ('guest_register', 'last_event'),
    ('guest_register', 'first_touch_at');

ALTER ROLE secretariat_reader
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE secretariat_reader SET default_transaction_read_only = on;

REVOKE ALL PRIVILEGES ON DATABASE :"secretariat_database" FROM secretariat_reader;
GRANT CONNECT ON DATABASE :"secretariat_database" TO secretariat_reader;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM secretariat_reader;
GRANT USAGE ON SCHEMA public TO secretariat_reader;

-- Remove stale table and column grants before rebuilding the exact read surface.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM secretariat_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM secretariat_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM secretariat_reader;

DO $revoke_columns$
DECLARE
    permission record;
BEGIN
    FOR permission IN
        SELECT DISTINCT table_schema, table_name, column_name
        FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_reader'
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES (%I) ON TABLE %I.%I FROM secretariat_reader',
            permission.column_name,
            permission.table_schema,
            permission.table_name
        );
    END LOOP;
END
$revoke_columns$;

GRANT SELECT (id, short_name, name, nip)
    ON TABLE public.companies TO secretariat_reader;
GRANT SELECT (id)
    ON TABLE public.client_registry TO secretariat_reader;
GRANT SELECT (user_id, company_id, is_active)
    ON TABLE public.user_companies TO secretariat_reader;
GRANT SELECT (
    company_id, effective_status, owner, service_scope, contract_ok,
    vat_whitelist_status, ksef_token_present, mismatch_vat, mismatch_status
)
    ON TABLE public.client_registry_v TO secretariat_reader;
GRANT SELECT (
    id, received_at, created_at, company_id, processing_status, email_type,
    sender_email, subject
)
    ON TABLE public.email_processing_registry TO secretariat_reader;
GRANT SELECT (id, company_id, title, owner, status, due_date, state, category)
    ON TABLE public.client_obligations TO secretariat_reader;
GRANT SELECT (
    id, company_id, to_address, subject, body, revisions, status, due_at, created_at,
    sent_log_id, error
)
    ON TABLE public.email_drafts TO secretariat_reader;
GRANT SELECT (id, sent_at, success, in_reply_to, error_message, automation_mode)
    ON TABLE public.email_send_log TO secretariat_reader;
GRANT SELECT (
    id, display_name, email, stage, next_action, next_action_owner, next_action_due,
    last_event, first_touch_at
)
    ON TABLE public.guest_register TO secretariat_reader;

DO $audit$
DECLARE
    unexpected_columns text;
    missing_columns text;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'secretariat_reader'
          AND (
              NOT rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolinherit
              OR rolreplication OR rolbypassrls
          )
    ) THEN
        RAISE EXCEPTION 'secretariat_reader has an unsafe role attribute';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members memberships
        JOIN pg_roles member_role ON member_role.oid = memberships.member
        WHERE member_role.rolname = 'secretariat_reader'
    ) THEN
        RAISE EXCEPTION 'secretariat_reader must not inherit privileges from another role';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'secretariat_reader'
          AND rolconfig @> ARRAY['default_transaction_read_only=on']
    ) THEN
        RAISE EXCEPTION 'secretariat_reader is not read-only by default';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.role_table_grants
        WHERE grantee = 'secretariat_reader'
    ) THEN
        RAISE EXCEPTION 'secretariat_reader has a relation-level privilege';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (
              has_table_privilege('secretariat_reader', relation.oid, 'SELECT')
              OR has_table_privilege('secretariat_reader', relation.oid, 'INSERT')
              OR has_table_privilege('secretariat_reader', relation.oid, 'UPDATE')
              OR has_table_privilege('secretariat_reader', relation.oid, 'DELETE')
              OR has_table_privilege('secretariat_reader', relation.oid, 'TRUNCATE')
              OR has_table_privilege('secretariat_reader', relation.oid, 'REFERENCES')
              OR has_table_privilege('secretariat_reader', relation.oid, 'TRIGGER')
          )
    ) THEN
        RAISE EXCEPTION 'secretariat_reader has an effective table-level privilege';
    END IF;

    WITH actual AS (
        SELECT table_name, column_name
        FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_reader'
          AND privilege_type = 'SELECT'
          AND table_schema = 'public'
    )
    SELECT string_agg(format('%I.%I', table_name, column_name), ', ' ORDER BY 1)
    INTO unexpected_columns
    FROM (
        SELECT * FROM actual
        EXCEPT
        SELECT * FROM secretariat_reader_allowed_columns
    ) difference;

    WITH actual AS (
        SELECT table_name, column_name
        FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_reader'
          AND privilege_type = 'SELECT'
          AND table_schema = 'public'
    )
    SELECT string_agg(format('%I.%I', table_name, column_name), ', ' ORDER BY 1)
    INTO missing_columns
    FROM (
        SELECT * FROM secretariat_reader_allowed_columns
        EXCEPT
        SELECT * FROM actual
    ) difference;

    IF unexpected_columns IS NOT NULL THEN
        RAISE EXCEPTION 'secretariat_reader has unexpected column grants: %', unexpected_columns;
    END IF;
    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'secretariat_reader is missing column grants: %', missing_columns;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_reader'
          AND privilege_type <> 'SELECT'
    ) THEN
        RAISE EXCEPTION 'secretariat_reader has a non-SELECT column privilege';
    END IF;
END
$audit$;

COMMIT;

SELECT 'secretariat_reader policy verified' AS result;
