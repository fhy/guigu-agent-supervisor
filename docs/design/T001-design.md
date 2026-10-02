# T001 Design Note

## Layout

`agent-run` is a small executable that imports modules from `src/`. Request and result
validation live in `protocol.py`, canonical path enforcement in `paths.py`, atomic
files and worktree locks in `state.py`, tmux ownership in `tmux.py`, and lifecycle
coordination in `supervisor.py`. `worker.py` runs inside tmux and invokes only the
fixed `mock` adapter.

## Process ownership

Every run receives a random hexadecimal ID and the tmux session name
`agent-<run-id>`. The session starts a fixed worker command; request-controlled values
are not included in that command. The state root and run ID are supplied as tmux
environment entries. Stop operations derive the exact session name from a validated
runtime record and reject records whose session name does not match the run ID.

## State and locking

Each run is stored beneath `runs/<run-id>`. JSON writes use a same-directory temporary
file, file flush and fsync, atomic replace, and parent-directory fsync where supported.
Directories are mode `0700` and files are mode `0600`.

A lock named from the SHA-256 digest of the canonical worktree is created with
`O_EXCL`. It contains the run ID and canonical worktree. The worker releases it only
when its run reaches a terminal state. CLI reconciliation may release a lock after an
owned tmux session has disappeared and the run has been classified as failed.

## Lifecycle and timeout

Start writes `preparing`, creates tmux, and succeeds only after the worker publishes
`running`. The worker applies the request timeout to the backend. A timeout terminates
the backend and records `failed` with exit code 124. A graceful stop sends Ctrl-C to
the exact session, then kills that session after a bounded wait and records
`cancelled` if necessary. Stopping a completed run changes only its resource state to
`stopped`; cancelled and failed classifications remain stable. Repeated stop is
idempotent.

## Redaction and logs

The backend receives a minimal allowlisted environment and no credential variables.
Diagnostics use fixed messages and never include prompt contents, environment values,
or raw backend output. Captured stdout and stderr are truncated to a fixed byte limit
before being retained.

## Test strategy

Unit tests cover strict schemas, result validation, path containment, symlink
rejection, atomic permissions, and lock exclusion. Process tests use real tmux for a
complete run, cancellation, duplicate worktree ownership, independent worktrees,
timeouts, stale-session classification, restart-style inspection, and protection of
an unrelated tmux session. All test state and worktrees are temporary.
