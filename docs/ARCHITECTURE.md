# Architecture

## Goal

Digital Secretariat gives the owner one private place to see what requires attention, inspect the
underlying evidence, and make an auditable decision. It is a control plane over existing systems,
not a second ERP and not an autonomous email bot.

## Modules

| Module | Responsibility | Trust level |
|---|---|---|
| Web control plane | Rendering, navigation, signed action tokens, status feedback | Private owner UI |
| Read model | Query operational projections with a column-scoped read-only role | Read-only database |
| Mail cache | Fetch RFC 822 messages with `BODY.PEEK[]` into mode `0600` cache files | IMAP credential holder |
| Action adapter | Translate UI commands to domain verbs | Narrow write role |
| Mail rail | Draft lifecycle, revision checks, freshness gate, kill switches | Audited domain boundary |
| SMTP gateway | Resolve credentials, send, append delivery evidence | Only outbound transport |
| Tailscale proxy | Authenticate the device/user and terminate private HTTPS | Network identity boundary |

The web application does not receive IMAP credentials. The browser does not control sender,
recipient, company linkage, or RFC threading headers. Outbound success is derived from the rail and
send log, never from an optimistic UI response.

## Reusable core and company adapter

The current 0.1 distribution contains a reference adapter for a PostgreSQL schema. A production
installation must map these ports explicitly:

- `DashboardRepository`: attention items, inbound register, obligations, relationships, calendar,
  performance, and source health.
- `DraftActions`: edit, release, and reject an existing draft with expected revision.
- `ReplyActions`: create a reply draft from an inbound registry ID, then optionally release it.
- `MessageReader`: retrieve sanitized plain text and attachment metadata from the private cache.

The next product milestone is moving the reference SQL and mail rail behind versioned packages so
upgrades do not require code copying between repositories.

## Deployment topology

```text
owner laptop / phone
        |
        | private HTTPS + Tailscale identity
        v
isolated Tailscale Serve identity
        |
        | localhost only
        v
FastAPI control plane :8040
   | read role       | action role             | cache files
   v                 v                         ^
PostgreSQL read   audited mail rail             |
                         |                read-only cache timer
                         v                         |
                    SMTP gateway <---------- IMAP accounts
```

## Productization contract

A company adapter is accepted only when it provides:

1. A schema/version probe that does not mutate data.
2. Column-level grants with an executable fail-closed audit.
3. Typed domain errors; the UI never parses exception strings.
4. Idempotent migrations with dry-run or disposable-database evidence.
5. A controlled internal-address E2E proving draft, approval, SMTP, and send-log linkage.
6. A rollback procedure that does not delete audit history.
