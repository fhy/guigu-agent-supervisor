# guigu-agent-supervisor

`guigu-agent-supervisor` is a small local runtime supervisor for task-scoped AI
agents. It launches an approved CLI backend, reports its runtime state, collects a
structured result, and drains or stops the process when the task is finished.

The supervisor does not choose project work, prioritize tasks, review code, or make
technical decisions. A Project Controller supplies a bounded request; the supervisor
executes it reliably.

## Initial milestone

The first milestone is a file-backed prototype with four commands:

```text
agent-run start <request.json>
agent-run status <run-id>
agent-run stop <run-id>
agent-run result <run-id>
```

It uses `tmux` for process continuity and a per-run directory for request, runtime,
logs and result artifacts. See [T001](docs/tasks/T001-minimal-supervisor-cli.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [File protocol](docs/PROTOCOL.md)
- [Security boundaries](docs/SECURITY.md)
- [Acceptance criteria](docs/ACCEPTANCE.md)
- [Task board](docs/TASK_BOARD.md)

## Non-goals for the prototype

No MCP server, A2A gateway, SQLite scheduler, distributed execution, arbitrary shell
API, secret injection, production operation, automatic task selection, or durable DAG
engine is part of T001.
