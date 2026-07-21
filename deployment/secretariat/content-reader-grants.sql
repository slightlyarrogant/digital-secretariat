\set ON_ERROR_STOP on

BEGIN;

DO $policy$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'secretariat_content_reader') THEN
        RAISE EXCEPTION 'Required role secretariat_content_reader does not exist';
    END IF;
END
$policy$;

ALTER ROLE secretariat_content_reader
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE secretariat_content_reader SET default_transaction_read_only = on;

REVOKE ALL PRIVILEGES ON DATABASE :"secretariat_database" FROM secretariat_content_reader;
GRANT CONNECT ON DATABASE :"secretariat_database" TO secretariat_content_reader;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM secretariat_content_reader;
GRANT USAGE ON SCHEMA public TO secretariat_content_reader;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM secretariat_content_reader;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM secretariat_content_reader;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public FROM secretariat_content_reader;

DO $revoke_columns$
DECLARE
    permission record;
BEGIN
    FOR permission IN
        SELECT DISTINCT table_schema, table_name, column_name
        FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_content_reader'
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES (%I) ON TABLE %I.%I FROM secretariat_content_reader',
            permission.column_name,
            permission.table_schema,
            permission.table_name
        );
    END LOOP;
END
$revoke_columns$;

GRANT SELECT (id, message_id, email_type, received_at, created_at)
    ON TABLE public.email_processing_registry TO secretariat_content_reader;
GRANT SELECT (
    id, email_address, imap_host, imap_port, imap_username, imap_password,
    processing_pipeline, is_active
)
    ON TABLE public.system_email_accounts TO secretariat_content_reader;

DO $audit$
DECLARE
    actual_count integer;
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = 'secretariat_content_reader'
          AND (
              NOT rolcanlogin OR rolsuper OR rolcreaterole OR rolcreatedb OR rolinherit
              OR rolreplication OR rolbypassrls
          )
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader has an unsafe role attribute';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_auth_members memberships
        JOIN pg_roles member_role ON member_role.oid = memberships.member
        WHERE member_role.rolname = 'secretariat_content_reader'
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader must not inherit another role';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.role_table_grants
        WHERE grantee = 'secretariat_content_reader'
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader has a relation-level privilege';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (
              has_table_privilege('secretariat_content_reader', relation.oid, 'SELECT')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'INSERT')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'UPDATE')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'DELETE')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'TRUNCATE')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'REFERENCES')
              OR has_table_privilege('secretariat_content_reader', relation.oid, 'TRIGGER')
          )
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader has an effective table-level privilege';
    END IF;
    SELECT COUNT(*) INTO actual_count
    FROM information_schema.column_privileges
    WHERE grantee = 'secretariat_content_reader' AND privilege_type = 'SELECT';
    IF actual_count <> 13 THEN
        RAISE EXCEPTION 'secretariat_content_reader expected 13 column grants, found %', actual_count;
    END IF;
    IF NOT (
        has_column_privilege(
            'secretariat_content_reader', 'public.email_processing_registry', 'message_id', 'SELECT'
        )
        AND has_column_privilege(
            'secretariat_content_reader', 'public.system_email_accounts', 'imap_password', 'SELECT'
        )
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader is missing required columns';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.column_privileges
        WHERE grantee = 'secretariat_content_reader' AND privilege_type <> 'SELECT'
    ) THEN
        RAISE EXCEPTION 'secretariat_content_reader has a non-SELECT column privilege';
    END IF;
END
$audit$;

COMMIT;

SELECT 'secretariat_content_reader policy verified' AS result;
