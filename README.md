# Digital Secretariat

Digital Secretariat is a private operational control plane for a small company. It turns inbound
mail, approval queues, obligations, relationships, deadlines, and delivery evidence into one owner
workspace available through a private Tailscale network.

This repository is the **0.1 reference distribution** extracted from a working deployment. It is
not yet a universal one-command SaaS installer. The UI and security boundary are reusable; every
company still needs a reviewed adapter mapping its source database, mailboxes, and outbound rail to
the contracts in this repository.

## Product rules

1. A message is not sent unless the audited send log proves success.
2. External mail requires an explicit human approval.
3. Missing or ambiguous data fails closed; the system does not guess joins, recipients, prices, or
   sender accounts.
4. The browser never supplies sender addresses or threading headers.
5. The web process receives no IMAP password. A separate read-only cache process handles mail.
6. AI may classify and prepare content, but untrusted inbound text is data, never an instruction.
7. Tailscale identity is the login boundary. The application accepts identity headers only from a
   configured local proxy.

## What is included

- Mobile-first FastAPI control plane under `src/secretariat/`.
- Reference PostgreSQL mail rail and SMTP gateway under `src/services/`.
- Least-privilege PostgreSQL policies and additive migrations under `deployment/` and `migrations/`.
- Hardened systemd templates and an atomic release deployer.
- Read-only preflight and installation verifier scripts.
- Human installation guide and an AI-led installation contract.
- Remotion production brief, shot list, and Polish voiceover script.

## Start here

- [Architecture](docs/ARCHITECTURE.md)
- [Manual installation](docs/INSTALLATION.md)
- [AI-led installation](docs/ai/README.md)
- [Security model](docs/SECURITY.md)
- [Operations and upgrades](docs/OPERATIONS.md)
- [Product video](docs/video/REMOTION_BRIEF.md)

For local UI development without write actions:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
SECRETARIAT_ALLOWED_LOGINS=owner@example.com \
SECRETARIAT_TRUSTED_PROXY_IPS=127.0.0.1 \
SECRETARIAT_DATABASE_URL=postgresql://reader@127.0.0.1/company \
uvicorn src.secretariat.app:app --host 127.0.0.1 --port 8040 --no-proxy-headers
```

The production service must never bind to `0.0.0.0`, accept public traffic, or enable action flags
before the database adapter and controlled internal-address test pass.

## Status

The reference UI and mail rail are tested. Productization work still includes a versioned adapter
SDK, schema-independent domain projections, a fully automated disposable-environment test, and a
customer-safe upgrade migrator. These gaps are explicit so an installer agent cannot silently
assume compatibility.
