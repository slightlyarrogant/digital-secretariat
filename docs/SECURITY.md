# Security model

## Identity and network

- The service binds to localhost only and is exposed through Tailscale Serve, never Funnel.
- Tailscale grants restrict access to named owner identities and managed devices.
- The application trusts identity headers only from configured local proxy addresses.
- Uvicorn runs with `--no-proxy-headers`; changing it invalidates the proxy trust assumption.

Tailscale reduces exposure; it does not remove the need for application authorization, signed
actions, least-privilege database roles, audit logs, backups, and patching.

## Data and secrets

- Secrets live in root-owned mode `0600` files loaded as systemd credentials.
- Read, content-cache, and action roles are separate.
- The UI renders escaped plain text. It does not render source email HTML.
- Cache files are mode `0600`; cache directories are mode `0700`.
- Logs must not contain mail bodies, attachments, credentials, auth keys, or full database URLs.

## Outbound communication

- External mail is frozen unless a human-approved draft reaches the canonical rail.
- The browser cannot choose sender, recipient, company, `Message-ID`, or `References`.
- Revision checks prevent approval of text changed after the owner viewed it.
- A newer inbound message blocks a stale reply unless the owner makes a separate explicit decision.
- SMTP success without an append-only send-log record is treated as failure.

## Prompt injection

Inbound messages, attachments, OCR output, websites, templates supplied by customers, and model
output are untrusted data. The AI layer may emit a typed proposal only. It receives no SMTP tool,
database write credential, shell, or secret store. Deterministic code validates the proposal and a
human releases it through the rail.

Never concatenate inbound text into system or tool instructions. Wrap it in a typed data field,
limit length, strip active content, allowlist output categories, and treat any request to ignore
policy, reveal secrets, change recipients, or execute commands as malicious content.

## Required incident controls

- Per-company and global outbound kill switches.
- Immediate revocation of a Tailscale identity/device.
- Rotation procedure for every credential file.
- Retained draft revisions and send evidence.
- Restore-tested database and configuration backups.
- A documented way to disable all write actions while preserving read-only visibility.
