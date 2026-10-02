# T001 Implementation Handoff

## Candidate

- Implementation commit: `e040cd667683a88a9fa7cb4febbc24af7b04f8d0`
- Base commit: `068b04b`
- Status: ready for independent review; not yet accepted
- Remote writes: none

## Delivered

- Executable `agent-run` with the frozen `start`, `status`, `stop`, and `result`
  commands and protocol exit codes.
- Strict File Protocol v1 request/result validation and canonical approved-root checks.
- Per-run file state, atomic JSON replacement, user-only permissions, and exclusive
  canonical-worktree locks.
- Exact tmux session ownership, startup handshake, stale-session reconciliation,
  graceful interrupt, bounded forced fallback, timeout handling, and idempotent stop.
- Deterministic `mock` adapter with no arbitrary command or environment interface.
- Credential-environment removal, fixed diagnostics, and bounded backend log capture.
- Unit and real-tmux process tests plus README usage documentation.

The candidate changes these areas:

- `agent-run`, `pyproject.toml`, and `src/agent_supervisor/`
- `tests/`
- `README.md`, `docs/TASK_BOARD.md`, and `docs/design/T001-design.md`

## Automated evidence

Run from the repository root on 2026-10-02 with Python 3.13.9 and tmux 3.4:

```text
ruff check .
All checks passed!

ruff format --check .
16 files already formatted

PYTHONPATH=src python3 -m unittest discover -v
Ran 18 tests in 7.367s
OK

git diff --check
(no output)
```

The real-tmux tests cover completion/result/stopped, graceful cancellation, forced
fallback, duplicate worktree exclusion, concurrent distinct worktrees, timeout,
malformed result, stale tmux disappearance and lock release, restart-style status,
unowned-session isolation, shell metacharacter safety, redaction, bounded logs, and
state permissions.

## Fresh-shell evidence

Executed from `bash --noprofile --norc` with a new temporary approved root and state
root. The temporary tree was removed after the run.

Completion lifecycle:

```text
start:  running (run 7b276f9c34944c18a0ad1073c3d491ce)
status: completed, exit_code 0
result: outcome succeeded, summary "final fresh-shell pass"
stop:   stopped
```

Cancellation lifecycle:

```text
start:  running (run ad7a048e5463434e9a5920c53b47c983)
stop:   cancelled, exit_code 130
status: cancelled
```

After tightening the interrupt target to the owned pane, the automated graceful-stop
test verifies completion within two seconds; a separate `remain-on-exit` test verifies
the three-second forced fallback removes the exact owned session. No tmux sessions were
left behind by the final suite.

## Limitations

- T001 includes only the deterministic mock backend and is not for production use.
- State reconciliation is command-driven; there is no daemon or automatic cleanup.
- State and bounded logs remain on disk until manually removed.
- The mock adapter runs inside the owned worker process; no Codex or OpenCode adapter is
  included.
- MCP, networking, SQLite, retries, scheduling, resume, and secret injection remain
  excluded.

## Review request

Independently review exact commit `e040cd667683a88a9fa7cb4febbc24af7b04f8d0`, rerun
the checks above, and repeat both lifecycles from a fresh shell. Keep T001 in `review`
until that candidate is accepted. Only after acceptance should the next experiment
specify a minimal stdio MCP wrapper over the supervisor application boundary.
