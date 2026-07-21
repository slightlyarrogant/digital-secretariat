import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_systemd_template_preserves_local_proxy_and_network_boundaries() -> None:
    unit = (ROOT / "systemd/digital-secretariat.service.in").read_text()

    assert "--host 127.0.0.1" in unit
    assert "--no-proxy-headers" in unit
    assert "CacheDirectory=digital-secretariat" in unit
    assert "SECRETARIAT_SNAPSHOT_FILE=/var/cache/digital-secretariat/dashboard.json" in unit
    assert "IPAddressDeny=any" in unit
    assert "@SMTP_IP_ALLOW_RULES@" in unit
    assert "SECRETARIAT_DRAFT_ACTIONS_ENABLED=true" not in unit
    assert "SECRETARIAT_REPLY_ACTIONS_ENABLED=true" not in unit


def test_deploy_is_atomic_and_keeps_migrations_outside_runtime_boundary() -> None:
    deploy = (ROOT / "deployment/secretariat/deploy.sh").read_text()

    assert 'archive --format=tar "$commit"' in deploy
    assert "Refusing to deploy a dirty worktree" in deploy
    assert "stat -c '%a'" in deploy
    assert "Unresolved placeholder" in deploy
    assert "Readiness failed; rolling back" in deploy
    assert "psql" not in deploy
    assert "migrations/manual" not in deploy


def test_email_measurement_migration_is_additive_and_evidence_based() -> None:
    migration = (ROOT / "migrations/manual/2026-07-19_email_measurement.sql").read_text()

    assert "ADD COLUMN IF NOT EXISTS automation_mode" in migration
    assert "automatic_template" in migration
    assert "formatted_approved" in migration
    assert "automatic_ai" in migration
    assert "DROP COLUMN" not in migration


def test_reader_grant_policy_is_column_scoped_and_fail_closed() -> None:
    policy = (ROOT / "deployment/secretariat/reader-grants.sql").read_text()

    for relation in (
        "companies",
        "client_registry",
        "user_companies",
        "client_registry_v",
        "email_processing_registry",
        "client_obligations",
        "email_drafts",
        "email_send_log",
        "guest_register",
    ):
        assert f"public.{relation} TO secretariat_reader" in policy

    assert "GRANT SELECT ON" not in policy
    assert "LOGIN NOSUPERUSER" in policy
    assert "NOBYPASSRLS" in policy
    assert "NOINHERIT" in policy
    assert "default_transaction_read_only = on" in policy
    assert "has_table_privilege" in policy
    assert "privilege_type <> 'SELECT'" in policy
    assert policy.startswith("\\set ON_ERROR_STOP on\n\nBEGIN;")
    assert "COMMIT;" in policy


def test_action_role_is_scoped_to_the_canonical_mail_rail() -> None:
    policy = (ROOT / "deployment/secretariat/action-grants.sql").read_text()
    unit = (ROOT / "systemd/digital-secretariat.service.in").read_text()

    assert "secretariat_action" in policy
    assert "LOGIN NOSUPERUSER" in policy
    assert "NOINHERIT" in policy
    assert "NOBYPASSRLS" in policy
    assert "GRANT SELECT (" in policy
    assert "GRANT UPDATE (" in policy
    assert "GRANT INSERT (" in policy
    assert "GRANT UPDATE ON" not in policy
    assert "GRANT INSERT ON" not in policy
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES" in policy
    assert "LoadCredential=action-database-url:" in unit
    assert "LoadCredential=action-token-secret:" in unit
    assert "SECRETARIAT_ACTION_SECRET_FILE=" in unit


def test_mail_cache_unit_separates_imap_access_from_web_process() -> None:
    web_unit = (ROOT / "systemd/digital-secretariat.service.in").read_text()
    cache_unit = (ROOT / "systemd/digital-secretariat-mail-cache.service.in").read_text()
    timer = (ROOT / "systemd/digital-secretariat-mail-cache.timer").read_text()

    assert "SECRETARIAT_CONTENT_DATABASE_URL_FILE" not in web_unit
    assert "SECRETARIAT_MAIL_CACHE=/var/cache/digital-secretariat-mail" in web_unit
    assert "LoadCredential=database-url:@CONFIG_ROOT@/content-database-url" in cache_unit
    assert "src.secretariat.mail_content --limit 200" in cache_unit
    assert "CacheDirectoryMode=0700" in cache_unit
    assert "OnUnitActiveSec=5min" in timer


def test_reference_distribution_contains_no_private_installation_defaults() -> None:
    forbidden_patterns = (
        re.compile(r"/home/[^/\s]+"),
        re.compile(r"\b\d{10,15}@s\.whatsapp\.net\b"),
        re.compile(r"\b[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net\b"),
    )
    roots = (ROOT / "src", ROOT / "systemd", ROOT / "deployment", ROOT / "docs")

    for directory in roots:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".sql", ".sh", ".in", ".yaml"}:
                content = path.read_text(encoding="utf-8")
                for pattern in forbidden_patterns:
                    assert pattern.search(content) is None, f"private default found in {path}"
