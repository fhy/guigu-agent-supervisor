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

## Local usage

Requirements are Python 3.11 or newer and `tmux`. No Python runtime packages are
required. From the repository root:

```text
./agent-run start /absolute/path/request.json \
  --approved-root /absolute/approved/root \
  --state-root /absolute/path/to/test-state
./agent-run status <run-id> --state-root /absolute/path/to/test-state
./agent-run result <run-id> --state-root /absolute/path/to/test-state
./agent-run stop <run-id> --state-root /absolute/path/to/test-state
```

`--state-root` is optional. Its default is
`${XDG_STATE_HOME:-$HOME/.local/state}/guigu-agent-supervisor/`. The request schema and
command output are defined in [the file protocol](docs/PROTOCOL.md). Only the
deterministic `mock` backend is included in T001; request JSON cannot supply a command,
executable, environment, or shell string.

On first use the supervisor creates the state root with mode `0700` and an ownership
marker. It refuses to adopt or change an existing unmarked directory. Existing state
roots created by an earlier prototype must therefore be moved aside or explicitly
removed by their owner before reuse.

Run the complete test suite with:

```text
PYTHONPATH=src python3 -m unittest discover -v
```

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
