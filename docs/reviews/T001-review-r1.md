# T001 Implementation Review R1

Verdict: `CHANGES_REQUESTED`

Reviewed candidate: `e040cd667683a88a9fa7cb4febbc24af7b04f8d0`

Review environment: Python 3.13.9, tmux 3.4, 2026-10-02.

## Findings

### P1: A caller-selected existing state directory is mutated and layout symlinks escape confinement

`safe_state_root` accepts any existing absolute directory and changes it to mode `0700`
when it has group/other permissions (`src/agent_supervisor/paths.py:48`). Passing an
existing directory such as a project root or another user-owned shared directory as
`--state-root` therefore changes that directory's permissions instead of refusing it.
`ensure_layout` then calls `mkdir(..., exist_ok=True)` and `chmod` on `runs` and `locks`
without rejecting symlinks or non-directories (`src/agent_supervisor/state.py:12`). An
existing `runs` or `locks` symlink can redirect supervisor state, locks and later
recursive cleanup outside the selected state root.

Required closure:

- distinguish creation of a new state root from adoption of an existing one;
- never chmod an existing caller-selected root to make it acceptable;
- require an exact supervisor-owned marker/identity before reusing an existing root;
- reject root ancestors/layout entries that resolve through symlinks, and reject
  non-directory or wrong-mode `runs`/`locks` entries;
- add process tests proving an unrelated existing directory retains its mode and bytes,
  and `runs`/`locks` symlink cases fail without external mutation.

### P1: Terminal reconciliation and worktree lock release are racy

`Supervisor._runtime` reads `runtime.json`, separately checks tmux, and may write
`failed` (`src/agent_supervisor/supervisor.py:75`). The worker independently writes its
terminal runtime and releases the worktree lock (`src/agent_supervisor/worker.py:110`).
A status call can read `running`, the worker can atomically publish `completed` and exit,
and the status call can then observe no tmux session and overwrite the terminal result
with `failed`.

`release_lock` also performs an unlocked read-then-unlink
(`src/agent_supervisor/state.py:85`). Two releasers can both read the old ownership;
after the first unlinks and a new run acquires the same path, the second can unlink the
new owner's lock. This breaks the one-writer guarantee.

Required closure:

- serialize runtime reconciliation, terminal publication and lock release per run or
  worktree with an OS-backed lock/CAS protocol;
- make lock release prove the same owned object at deletion time, not only before it;
- preserve an already-published terminal state when tmux disappears;
- add deterministic race-seam tests for terminal publish versus status/stop and old
  owner release versus new owner acquisition.

### P1: Prompt no-symlink validation is subject to replacement before execution

The CLI validates and resolves the prompt path (`src/agent_supervisor/protocol.py:76`),
stores that path in `request.json`, and the worker/backend opens it later
(`src/agent_supervisor/backends/mock.py:22`). Nothing binds the executed bytes or inode
to the object that passed validation. The file can be replaced with a symlink or a
different regular file after `start` validation and before backend open, defeating the
frozen prompt path/type/size checks.

Required closure:

- copy or open/snapshot the prompt with no-follow semantics during admission and bind
  the worker to the supervisor-owned snapshot;
- validate the exact snapshotted bytes and size before launching tmux;
- add a deterministic pre-open replacement test covering symlink and oversized-content
  substitution, with no outside-file read or disclosure.

## Verification

The following checks passed on the reviewed tree:

```text
ruff check .                                           exit 0
ruff format --check .                                  exit 0
PYTHONPATH=src python3 -m unittest discover -v         exit 0, 18 tests
python3 -m compileall -q src tests                     exit 0
git diff --check 068b04b..e040cd6                     exit 0
```

The existing tests substantiate the reported nominal lifecycle, timeout, cancellation,
basic lock exclusion, bounded ASCII logs, redacted CLI errors and unowned tmux-session
isolation. They do not exercise the three findings above.

## Frozen R1 Closure Matrix

Only these T001 issues block R2:

1. existing-root/layout no-follow ownership and no-mutation behavior;
2. serialized terminal reconciliation and ownership-safe lock release;
3. admitted prompt snapshot/no-follow binding.

MCP, SQLite, A2A, real Codex/OpenCode adapters, session resume, automatic cleanup and
project scheduling remain excluded. R2 must review a new exact implementation commit
and an updated handoff; the existing nominal and security matrix must remain green.
