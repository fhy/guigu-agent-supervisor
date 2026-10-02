# T001: Minimal File-Backed Supervisor CLI

Status: queued
Owner: unassigned
Priority: first prototype

## Goal

Implement the smallest safe local experiment proving that a bounded request can launch
a task-scoped CLI Agent, survive terminal detachment through tmux, expose runtime state,
collect a structured result and stop the owned process.

## Frozen CLI

```text
agent-run start <request.json> --approved-root <absolute-path> [--state-root <path>]
agent-run status <run-id> [--state-root <path>]
agent-run stop <run-id> [--state-root <path>]
agent-run result <run-id> [--state-root <path>]
```

Commands and output follow `docs/PROTOCOL.md`. T001 must provide a deterministic mock
backend. A real Codex adapter is optional and cannot replace mock process tests.

## Implementation constraints

- Prefer Python 3.11+ standard library and no runtime dependency beyond tmux.
- Keep process management, protocol validation and backend adapters separated.
- No arbitrary executable or command field is accepted from request JSON.
- No daemon, network listener or background service is added.
- No credentials or production paths are used.
- State writes use same-directory temporary files, flush/fsync, atomic replace and
  parent-directory fsync where supported.
- A per-worktree exclusive lock prevents two active writer runs.
- Log capture is bounded; status and errors remain redacted.

## Deliverables

- executable `agent-run` entry point;
- source modules and deterministic mock backend;
- unit and real-tmux process tests;
- README installation and usage update;
- `docs/handoffs/T001-handoff.md` with exact candidate evidence.

## Exclusions

- MCP server or tools;
- SQLite or event-sourced task database;
- A2A or Matrix;
- multi-host execution;
- Project Controller logic or automatic role selection;
- automatic retries or DAG scheduling;
- session resume;
- secret injection;
- production use;
- automatic cleanup of user state;
- systemd services.

## Acceptance

All cases in `docs/ACCEPTANCE.md` pass. The implementation must demonstrate one complete
mock lifecycle:

```text
start -> running -> result available -> completed -> stop/idempotent stop
```

and one cancellation lifecycle:

```text
start -> running -> stop -> cancelled/stopped
```

No MCP work begins until an independent review accepts the exact T001 candidate and the
prototype has been exercised manually from a fresh shell.

## First action

The implementing Agent reads all project documents, records a short design note covering
module layout, tmux ownership, atomic state updates, lock lifecycle, timeout handling,
redaction and tests, then implements the full bounded task without adding excluded
capabilities.
