# Normative AI installation contract

## Installation states

`DISCOVERY -> PLANNED -> APPROVED -> READ_ONLY -> PRIVATE_ACCESS -> ACTIONS_TESTED -> ACCEPTED`

The agent may move forward only with evidence for the current state. A failed check moves the stage
to `DIAGNOSING`; it does not skip the check.

## Mandatory human gates

| Gate | Approval covers | Approval does not cover |
|---|---|---|
| G1 host changes | listed packages and users | database/Tailscale/mail changes |
| G2 data layer | exact roles, SQL hashes, target database | enabling actions or SMTP |
| G3 private network | exact grants, tag, service and Serve commands | Funnel or public exposure |
| G4 actions | enabling named action flags | external recipients |
| G5 mail E2E | one named internal recipient and exact subject prefix | customer addresses |

Approvals are specific and expire when the plan changes materially.

## Required artifacts

- Append-only installation log, root-owned mode `0600`, outside Git.
- Sanitized environment inventory and adapter map.
- SQL hashes and disposable-database results.
- Rendered systemd units with no unresolved placeholders.
- Release SHA and rollback SHA.
- Tailscale policy diff and allowed/denied test results.
- Internal-address E2E evidence linking inbound registry, draft revision, send log, and SMTP message ID.

## Acceptance matrix

| Check | Required result |
|---|---|
| Git | clean, reviewed release SHA |
| Tests | Secretariat and rail suites pass |
| Secrets scan | no credentials, private keys, personal numbers, or auth keys in Git |
| Listener | exactly `127.0.0.1:<port>` |
| Direct unauthenticated HTTP | `401` |
| Disallowed tailnet identity/device | denied |
| Allowed owner | private HTTPS works |
| Database read role | read-only, column-scoped, no role inheritance/BYPASSRLS |
| Content role | only message lookup and active IMAP account fields |
| Action role | only canonical rail tables/columns |
| Browser payload | no sender, recipient, company, Message-ID, or References |
| Stale revision | rejected without SMTP |
| Newer inbound | blocked without separate decision |
| SMTP failure | visible failed draft, no false success |
| Internal mail success | send log and message threading evidence agree |
| Rollback | previous release restores and becomes ready |

## Stop conditions

Stop and mark `INSTALLATION INCOMPLETE` when there is no current backup, the schema cannot be mapped
without guessing, the owner identity is ambiguous, secrets have been exposed, a required control
would need weakening, provider network destinations cannot be constrained, or an irreversible
operation lacks explicit approval.
