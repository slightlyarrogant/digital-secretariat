# Manual installation

This guide describes the reference Ubuntu/systemd/PostgreSQL deployment. Read the architecture and
security model first. For an installation led by a coding agent, use `docs/ai/README.md` instead of
improvising from this page.

## 1. Prerequisites

- Ubuntu or another systemd-based Linux host.
- Python 3.11, Git, PostgreSQL client tools, OpenSSL, curl, and Tailscale.
- A PostgreSQL database whose adapter contract has been reviewed.
- Three separate database credentials: read model, mail-content cache, and action rail.
- An owner-controlled internal email address for E2E testing.

Run the non-mutating check:

```bash
./scripts/preflight.sh
```

## 2. Install code and dependencies

```bash
sudo install -d -o root -g root -m 0755 /opt/digital-secretariat
sudo python3.11 -m venv /opt/digital-secretariat/venv
sudo /opt/digital-secretariat/venv/bin/pip install --upgrade pip
sudo /opt/digital-secretariat/venv/bin/pip install -e '.[dev]'
```

For a reproducible customer release, replace editable installation with a pinned wheel and hashes.
The 0.1 repository intentionally does not pretend that dependency locking is finished.

## 3. Prepare configuration without committing secrets

Create `/etc/digital-secretariat` as `root:root` mode `0700`. Store the following raw, single-line
credential files as `root:root` mode `0600`:

- `database-url`: read-model PostgreSQL URL.
- `content-database-url`: message lookup and IMAP-account reader URL.
- `action-database-url`: mail-rail PostgreSQL URL.
- `action-token-secret`: 32 random bytes encoded as 64 hexadecimal characters.

Create `secretariat.env` from `.env.example`, mode `0600`. Do not put database passwords, SMTP
passwords, API keys, or Tailscale auth keys in it.

Create `/etc/digital-secretariat/install.conf` from `install.conf.example`. Resolve the actual SMTP
provider destination addresses and list the reviewed IP/CIDR values in `SMTP_IP_ALLOW`. Provider IPs
can change; record the evidence and operational update procedure.

## 4. Adapt and verify the database

The SQL files under `deployment/secretariat/` are a reference contract, not a license to run them
against an unknown schema. First query `information_schema` and `pg_catalog`, compare every required
column and view, and test the policies on a disposable database clone.

Keep write flags disabled:

```dotenv
SECRETARIAT_DRAFT_ACTIONS_ENABLED=false
SECRETARIAT_REPLY_ACTIONS_ENABLED=false
SECRETARIAT_OUTBOUND_FREEZE=true
```

Only after reviewed migration evidence may an administrator apply additive migrations and the
column-scoped grants. Production SQL changes require a separate human approval.

The grant scripts require the target database name as a psql variable, for example:

```bash
psql -X --dbname="$ADMIN_DATABASE_URL" --set=ON_ERROR_STOP=1 \
  --set=secretariat_database=company_database \
  < deployment/secretariat/reader-grants.sql
```

## 5. Deploy the read-only control plane

Commit all reviewed configuration templates but no secrets. From a clean checkout:

```bash
sudo deployment/secretariat/deploy.sh /etc/digital-secretariat/install.conf
PORT=8040 ./scripts/verify-install.sh
```

The listener must be exactly `127.0.0.1:8040`. A `0.0.0.0` listener is a failed install.

## 6. Publish privately with Tailscale

Use an isolated tag-owned Tailscale daemon and Tailscale Serve. Do not enable Funnel. Grant the
owner identity access only to HTTPS 443 on the service/tag. The Serve proxy must be the only source
of `Tailscale-User-*` headers accepted by the application.

Verify three paths:

1. Allowed owner device: dashboard loads over private HTTPS.
2. Tailnet device outside the grant: connection is denied.
3. Direct localhost request without forwarded identity: application returns `401`.

## 7. Enable decisions in two gates

First enable draft editing/approval and run an internal-address E2E. Then, separately, enable inline
inbound replies after the source mailbox mapping and RFC threading tests pass. Never test with a
customer address.

## 8. Record and hand off

Store an append-only sanitized installation log outside the repository. It must include versions,
decisions, approvals, commands, exit codes, health evidence, rollback target, and unresolved risks.
Use `docs/ai/INSTALLATION_LOG_TEMPLATE.md` as the format even for a manual installation.
