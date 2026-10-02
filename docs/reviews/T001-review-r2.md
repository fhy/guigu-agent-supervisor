# T001 Implementation Review R2

Verdict: `PASS`

Reviewed candidate: `e40d95bf47545c555e3642fcfb12d45fc5323573`

Reviewed handoff: `2bd9a1f5e83354ee7389d8ad6b4786fe758baaa5`

Review environment: Python 3.13.9, tmux 3.4, 2026-10-02.

## Frozen R1 Closure Matrix

### Existing-root and layout confinement

Accepted. A new state root receives an exact ownership marker. Reuse requires that
marker, a real mode `0700` root, and real mode `0700` `runs` and `locks`
directories. Existing unmarked or incorrectly permissioned directories are rejected
without chmod, and symlink ancestors/layout entries are rejected without external
mutation.

### Terminal reconciliation and lock release

Accepted. Runtime publication, reconciliation and stop updates use the same per-run
`flock`. Worktree acquisition and release use the same persistent per-worktree guard;
release verifies owner data and the opened lock inode while holding that guard. The
deterministic terminal/status, terminal/stop and old/new owner tests passed five
consecutive review runs.

### Prompt admission binding

Accepted. Admission opens the canonical prompt with `O_NOFOLLOW`, validates the opened
regular file and bounded bytes, and atomically writes a private snapshot before tmux
launch. The worker reads only that snapshot. Process tests confirm later symlink and
oversized replacements do not affect execution or disclose outside content.

## Verification

```text
ruff check .                                           exit 0
ruff format --check .                                  exit 0
python3 -m compileall -q src tests                     exit 0
PYTHONPATH=src python3 -m unittest discover -v         exit 0, 25 tests
focused race suite, five consecutive runs              exit 0
git diff --check                                       exit 0
```

A fresh-shell real-tmux lifecycle also passed:

```text
start -> running -> completed -> succeeded result -> stopped
```

The result summary was `R2 fresh shell`; no owned tmux session remained after review
cleanup.

## Scope

No findings remain in the frozen R1 closure matrix. This verdict does not authorize or
review MCP, SQLite, A2A, real Agent adapters, scheduling, resume, automatic cleanup or
production use. Those remain separate future tasks.
