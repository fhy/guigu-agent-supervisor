# Architecture

## Responsibility boundary

```text
Project Controller
  decides role, task, scope and expected result
        |
        | request.json
        v
Agent Supervisor
  launches, observes, drains and collects
        |
        v
Task-scoped CLI Agent
```

The Project Controller owns project semantics. The supervisor owns process facts.
Process exit does not mean that a project task passed review or is done.

## T001 components

```text
agent-run CLI
  -> request validation
  -> approved backend adapter
  -> tmux session
  -> per-run artifact directory
```

Default state root:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/guigu-agent-supervisor/
```

Each run is isolated under `runs/<run-id>/`. T001 supports one active writer per
canonical worktree. A lock file created with exclusive creation binds the worktree to
the run until the process is terminal and drained.

## Runtime states

```text
requested -> preparing -> running -> draining -> completed -> stopped
                         |           |
                         +-> failed <-+
                         +-> cancelled
```

`completed` means the process exited successfully and a valid result exists. `failed`
means startup, execution, protocol validation or result collection failed. `stopped`
is a post-terminal resource state, not a project-task verdict.

## Backend boundary

Backends are named adapters, never caller-supplied shell commands. T001 must include a
deterministic mock adapter used by tests. Codex and OpenCode adapters may be included
only through fixed argv construction with no shell evaluation.

## Later evolution

If T001 succeeds, later tasks may wrap the CLI as MCP tools, replace file indexes with
SQLite, add restart reconciliation and resource budgets, and store compact Controller
checkpoints. Those capabilities are not part of T001.
