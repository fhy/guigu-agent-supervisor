# Security Boundaries

## Trust model

T001 is a local development prototype. It is not authorized for production operations
or credentials. Requests and prompt files are trusted project inputs, but still require
strict schema and path validation.

## Required controls

- Use argv arrays and direct process execution; never use `shell=True`, `eval`, `bash
  -c`, interpolated shell strings or caller-supplied executable paths.
- Backend names map to fixed, reviewed executable and argument builders.
- Canonicalize approved roots, worktree and prompt paths; reject symlinks and escapes.
- Create state/run files with user-only permissions.
- Use generated run IDs and supervisor-generated tmux session names.
- Reject duplicate active ownership of one worktree.
- Bound prompt size, result size, timeout and retained log size.
- Do not inherit credential variables by default. T001 has no secret-injection feature.
- Never return prompt contents, environment values or raw backend output from status or
  result-validation errors.
- Stop the entire owned process group/session, never a PID discovered by broad matching.

## Stop behavior

`stop` sends a graceful interrupt to the exact owned tmux session, waits a bounded
interval, then terminates that session if it remains alive. It must be idempotent for a
terminal run and must never affect an unowned tmux session.

## Retention

T001 retains request metadata, bounded logs, runtime state and result beneath the state
root for manual inspection. It provides no automatic deletion. Tests use a temporary
state root and remove only their own generated directory.
