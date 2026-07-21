# AI-led installation

The AI installer is a supervised operator, not a blind shell script. It inspects the host and source
systems, proposes an evidence-based plan, repairs ordinary dependency problems, and maintains an
append-only installation log. Human approval remains mandatory for security boundaries and writes.

## How to use

1. Clone this repository on the target host.
2. Start Codex or another coding agent in the repository root with filesystem and terminal access.
3. Paste the contents of `INSTALLER_PROMPT.md` as the task.
4. Answer the agent's questions about owner identity, source systems, domain, and internal test
   address. Enter secrets only through local secret prompts/files, never chat.
5. Review every gate labelled `HUMAN APPROVAL REQUIRED`.
6. Keep the resulting log outside the repository and give the sanitized handoff to support.

The normative behavior is in `INSTALLATION_CONTRACT.md`. `install-manifest.yaml` provides the same
stages in a machine-readable form. An agent that cannot follow the contract must stop and hand off;
it must not improvise a weaker installation.
