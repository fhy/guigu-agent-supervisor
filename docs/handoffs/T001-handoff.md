# T001 Implementation Handoff

## Candidate

- R2 implementation candidate: `e40d95bf47545c555e3642fcfb12d45fc5323573`
- Original R1 candidate: `e040cd667683a88a9fa7cb4febbc24af7b04f8d0`
- R1 review commit: `4fd4a3d7da8dbb230e6c35114017238a074a7aca`
- Base commit: `068b04b`
- Status: R1 changes closed; ready for independent R2 review; not yet accepted
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

## R1 closure

The R2 candidate closes only the three findings frozen in
`docs/reviews/T001-review-r1.md`:

- State roots now require a private mode and exact ownership marker. Existing unmarked
  directories are rejected without chmod or content changes. Root ancestors and
  `runs`/`locks` entries reject symlinks; existing layout directories must be mode
  `0700`.
- Runtime terminal publication, reconciliation, and stop updates are serialized by a
  per-run OS lock. Worktree owner acquisition/release is serialized by a persistent
  guard, and deletion checks the owner plus opened inode while holding that guard.
- Start snapshots the admitted prompt with `O_NOFOLLOW`, regular-file and size checks
  before tmux launch. The worker consumes only the private snapshot.

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
Ran 25 tests in 8.887s
OK

git diff --check
(no output)
```

The real-tmux tests cover completion/result/stopped, graceful cancellation, forced
fallback, duplicate worktree exclusion, concurrent distinct worktrees, timeout,
malformed result, stale tmux disappearance and lock release, restart-style status,
unowned-session isolation, shell metacharacter safety, redaction, bounded logs, and
state permissions, state-root ownership/non-mutation, layout symlink and mode
rejection, deterministic runtime/stop/lock race seams, and prompt replacement after
admission. The three race tests also passed five consecutive focused runs.

## Fresh-shell evidence

Executed from `bash --noprofile --norc` with a new temporary approved root and state
root. The temporary tree was removed after the run.

Completion lifecycle:

```text
start:  running (run ce90810dbe094caa9fba3946097d37cf)
status: completed, exit_code 0
result: outcome succeeded, summary "R1 closure fresh-shell pass"
stop:   stopped
```

Cancellation lifecycle:

```text
start:  running (run 5c49207f925646089cfb1502775f42dc)
stop:   cancelled
```

After tightening the interrupt target to the owned pane, the automated graceful-stop
test verifies completion within two seconds; a separate `remain-on-exit` test verifies
the three-second forced fallback removes the exact owned session. No tmux sessions were
left behind by the final suite.

## Limitations

- T001 includes only the deterministic mock backend and is not for production use.
- State reconciliation is command-driven; there is no daemon or automatic cleanup.
- State and bounded logs remain on disk until manually removed.
- Unmarked state directories from the pre-R2 prototype are intentionally not adopted;
  their owner must move or remove them explicitly before reusing the same path.
- The mock adapter runs inside the owned worker process; no Codex or OpenCode adapter is
  included.
- MCP, networking, SQLite, retries, scheduling, resume, and secret injection remain
  excluded.

## Review request

Independently review exact commit `e40d95bf47545c555e3642fcfb12d45fc5323573`, rerun
the checks above, and repeat both lifecycles from a fresh shell. R2 should verify only
the frozen closure matrix plus regression of the existing gates. Keep T001 in `review`
until that candidate is accepted. Only after acceptance should the next experiment
specify a minimal stdio MCP wrapper over the supervisor application boundary.
