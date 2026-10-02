# Agent Entry Protocol

Read `docs/TASK_BOARD.md`, then the active task specification and the documents it
links. The task specification is authoritative for scope and acceptance.

The project goal is to validate a minimal local Agent runtime supervisor before
building an MCP interface or durable scheduling core.

Rules:

- Keep T001 small. Do not add SQLite, MCP, A2A, networking or a daemon.
- Do not expose an arbitrary command or shell-string execution interface.
- Do not read, inject, print or persist credentials.
- Restrict all paths to explicitly approved canonical roots.
- Treat project task state and Agent process state as separate concepts.
- Use explicit file staging; never use `git add .`, `git add -A` or `git add -u`.
- Preserve user changes and do not perform remote writes unless explicitly requested.
- A completed implementation includes tests, exact commit and a handoff.

The implementation Agent may select ordinary internal details within the frozen T001
contract. Any change to the CLI, JSON protocol, security boundary or non-goals requires
a documented clarification before implementation.
