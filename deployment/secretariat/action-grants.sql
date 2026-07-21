\set ON_ERROR_STOP on

BEGIN;

DO $policy$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'secretariat_action') THEN
        RAISE EXCEPTION 'Required role secretariat_action does not exist';
    END IF;
END
$policy$;

ALTER ROLE secretariat_action
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE secretariat_action RESET default_transaction_read_only;

REVOKE ALL PRIVILEGES ON DATABASE :"secretariat_database" FROM secretariat_action;
GRANT CONNECT ON DATABASE :"secretariat_database" TO secretariat_action;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM secretariat_action;
GRANT USAGE ON SCHEMA public TO secretariat_action;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM secretariat_action;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM secretariat_action;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM secretariat_action;

GRANT SELECT (
    id, company_id, from_address, to_address, cc_addresses, subject, body, body_html, attachments,
    log_category, status, due_at, created_by, created_at, decided_at, decision_via,
    sent_log_id, error, revisions
)
    ON TABLE public.email_drafts TO secretariat_action;
GRANT UPDATE (
    subject, body, status, decided_at, decision_via, sent_log_id, error, revisions
)
    ON TABLE public.email_drafts TO secretariat_action;

GRANT SELECT (id, smtp_message_id)
    ON TABLE public.email_send_log TO secretariat_action;
GRANT INSERT (
    from_address, to_address, cc_addresses, subject, body_preview,
    attachments_metadata, company_id, log_category, smtp_message_id, success,
    error_message, in_reply_to, sent_by, automation_mode, template_key, template_version
)
    ON TABLE public.email_send_log TO secretariat_action;
GRANT USAGE, SELECT ON SEQUENCE public.email_send_log_id_seq TO secretariat_action;

GRANT SELECT (email_address, is_active, smtp_host, smtp_port, smtp_username, smtp_password)
    ON TABLE public.system_email_accounts TO secretariat_action;
GRANT SELECT (company_id, category)
    ON TABLE public.mail_rail_optouts TO secretariat_action;

DO $audit$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'secretariat_action'
          AND (
              NOT rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolinherit
              OR rolreplication OR rolbypassrls
          )
    ) THEN
        RAISE EXCEPTION 'secretariat_action has an unsafe role attribute';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members memberships
        JOIN pg_roles member_role ON member_role.oid = memberships.member
        WHERE member_role.rolname = 'secretariat_action'
    ) THEN
        RAISE EXCEPTION 'secretariat_action must not inherit privileges from another role';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.role_table_grants
        WHERE grantee = 'secretariat_action'
    ) THEN
        RAISE EXCEPTION 'secretariat_action has a relation-level privilege';
    END IF;
END
$audit$;

COMMIT;

SELECT 'secretariat_action policy verified' AS result;
