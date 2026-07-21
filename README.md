# Digital Secretariat

Digital Secretariat is the communication control plane for an AI-operated company. It gives every
agent and operator one shared account of what the company received, what it promised, what requires
a decision, and what was actually sent. Its purpose is to prevent legacy jobs, new agents, and human
operators from creating parallel, invisible versions of the company's relationship with a client.

This repository is the **0.1 reference distribution** extracted from a working deployment. It is
not yet a universal one-command SaaS installer. The UI and security boundary are reusable; every
company still needs a reviewed adapter mapping its source database, mailboxes, and outbound rail to
the contracts in this repository.

## How we used Codex and GPT-5.6

### Codex

We used Codex as an engineering partner, not only as a code generator. It inspected the existing
company system and traced failures across the owner interface, PostgreSQL state, mail rail,
Tailscale identity proxy, and systemd deployment. That investigation helped turn real incidents -
including invisible client conversations, stale drafts, approval failures, and uncontrolled legacy
send paths - into explicit product invariants.

Codex then helped us extract the reusable control plane into this standalone repository, implement
and debug the approval workflows, build focused regression tests, sanitize company-specific data,
document the security model, and prepare CI, deployment, rollback, and AI-guided installation
contracts. The installer design applies the same approach operationally: inspect an error, explain
the diagnosis, request approval for consequential changes, rerun verification, and append evidence
to the installation log.

### GPT-5.6

We used GPT-5.6 for bounded reasoning over unstructured client communication. It helped classify
intent, identify missing or conflicting context, and prepare concise proposed replies using approved
company knowledge and templates. This is the part of the workflow where language understanding is
valuable; trusted addressing, revisions, permissions, and delivery remain deterministic.

GPT-5.6 never becomes the final authority. Inbound messages and model output are treated as
untrusted data. The model receives no SMTP capability, database write credential, shell, or secret
store. Its proposal must pass deterministic validation and the same human approval rail as any
other draft before an external message can be released. The public reference distribution excludes
model credentials and company-specific orchestration while preserving this typed proposal boundary.

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

Product message: **One company. One client interface. No invisible promises.** See
[`docs/POSITIONING.md`](docs/POSITIONING.md) for the claim hierarchy and proof boundaries.

## What is included

- Mobile-first FastAPI control plane under `src/secretariat/`.
- Reference PostgreSQL mail rail and SMTP gateway under `src/services/`.
- Least-privilege PostgreSQL policies and additive migrations under `deployment/` and `migrations/`.
- Hardened systemd templates and an atomic release deployer.
- Read-only preflight and installation verifier scripts.
- Human installation guide and an AI-led installation contract.
- English-only Remotion production brief, shot list, and master voiceover script.

## Start here

- [Architecture](docs/ARCHITECTURE.md)
- [Positioning and sales message](docs/POSITIONING.md)
- [Hackathon submission](docs/SUBMISSION.md)
- [English-only language policy](docs/LANGUAGE_POLICY.md)
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

The reference UI and mail rail are tested. The current extracted UI still contains legacy Polish
strings; this is known migration debt and the next product release is blocked until the
English-only policy is enforced. Productization work also includes a versioned adapter
SDK, schema-independent domain projections, a fully automated disposable-environment test, and a
customer-safe upgrade migrator. These gaps are explicit so an installer agent cannot silently
assume compatibility.
