# Operations and upgrades

## Daily checks

- `/health/ready` is green and the source-freshness view is current.
- Mail-cache timer succeeded without exposing IMAP credentials to the web process.
- Pending approvals, failed drafts, bounces, and overdue obligations are visible.
- No unexplained change occurred in Tailscale grants, tags, or service hosts.

## Upgrade sequence

1. Read release notes and adapter contract changes.
2. Back up the database and root-owned configuration; verify restore instructions.
3. Run tests and schema probes against a disposable clone.
4. Keep outbound freeze enabled during deployment.
5. Deploy a committed release; readiness failure automatically restores the previous symlink.
6. Verify allowed and denied network paths.
7. Run a controlled internal-address mail test when the release touches the rail.
8. Record evidence and the rollback release SHA in the append-only log.

Customized installations should update infrequently and deliberately. An AI installer may diagnose
version drift and prepare an upgrade plan, but it may not overwrite company adapters, run migrations,
or re-enable sends without a reviewed diff and explicit approval.

## Emergency stop

Set both action feature flags to `false`, keep `SECRETARIAT_OUTBOUND_FREEZE=true`, restart the web
service, and verify read-only access remains available. If network identity is suspect, remove the
Tailscale grant or service advertisement as well.
