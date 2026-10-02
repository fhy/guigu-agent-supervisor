# File Protocol v1

All JSON is UTF-8, object-shaped and written atomically. Unknown fields are rejected in
T001 so later protocol changes require an explicit version increment.

## Request

```json
{
  "format": 1,
  "project_id": "example-project",
  "task_id": "T001",
  "role": "architect-developer",
  "backend": "mock",
  "worktree": "/absolute/approved/worktree",
  "prompt_file": "/absolute/approved/worktree/prompts/T001.md",
  "timeout_seconds": 300,
  "expected_result": "handoff"
}
```

Validation:

- identifiers use `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`;
- `format` is exactly `1`;
- `role`, `backend` and `expected_result` are fixed supported enums;
- timeout is between 1 and 86400 seconds;
- worktree exists, is a directory and resolves beneath an configured approved root;
- prompt is a regular non-symlink file within the canonical worktree;
- duplicate active worktree ownership is rejected;
- request data is never interpreted by a shell.

## Start response

```json
{
  "format": 1,
  "run_id": "generated-id",
  "state": "running"
}
```

`start` is successful only after the tmux session and runtime record are observable.

## Runtime record

`runtime.json` contains only supervisor facts:

```json
{
  "format": 1,
  "run_id": "generated-id",
  "state": "running",
  "tmux_session": "agent-generated-id",
  "started_at": "RFC3339 timestamp",
  "finished_at": null,
  "exit_code": null
}
```

Atomic updates must not expose partially written JSON.

## Agent result

The launched Agent writes `result.json` through an adapter-provided result path:

```json
{
  "format": 1,
  "run_id": "generated-id",
  "outcome": "succeeded",
  "summary": "bounded plain-text summary",
  "commit": "optional 40-character lowercase Git SHA",
  "artifact": "optional worktree-relative path"
}
```

Allowed outcomes are `succeeded`, `needs_clarification`, `blocked` and `failed`.
`summary` is limited to 4096 UTF-8 bytes. An artifact resolves inside the worktree and
must be a regular non-symlink file. Result contents do not change project task state.

## Command output

Every command emits exactly one JSON object on stdout. Diagnostics go to stderr and
must not include prompt contents, backend output or environment values. Exit codes:

```text
0 success
2 invalid arguments or request
3 unsafe path or ownership conflict
4 run not found
5 invalid state transition
6 backend/process failure
7 result unavailable or malformed
```
