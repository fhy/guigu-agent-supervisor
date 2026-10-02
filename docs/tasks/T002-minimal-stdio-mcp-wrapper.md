# T002: Minimal stdio MCP Wrapper

Status: review
Owner: implementation agent
Priority: next experiment after accepted T001

## Goal

Expose the accepted T001 supervisor application boundary as four local MCP tools over
stdio, without changing T001 process semantics or adding a scheduler, network service,
credential channel, or arbitrary execution interface.

## Frozen server CLI

```text
agent-mcp --approved-root <absolute-path> [--state-root <absolute-path>]
```

The server supports stdio transport only. It writes MCP protocol messages only to
stdout. Fixed diagnostics may be written to stderr. `--approved-root` and
`--state-root` are process configuration and are never accepted from an MCP tool call.

T002 uses the official Python MCP SDK pinned to `mcp==1.28.1`. An SDK major-version
upgrade is outside T002.

## Frozen tools

No MCP resources, prompts, sampling, elicitation, roots negotiation, or additional
tools are included.

### `agent_start`

Input is the File Protocol v1 request object itself:

```json
{
  "format": 1,
  "project_id": "example-project",
  "task_id": "T002",
  "role": "architect-developer",
  "backend": "mock",
  "worktree": "/absolute/approved/worktree",
  "prompt_file": "/absolute/approved/worktree/prompts/T002.md",
  "timeout_seconds": 300,
  "expected_result": "handoff"
}
```

All fields are required and unknown fields are rejected. The wrapper validates the
same enums, limits and canonical paths as `agent-run start`, atomically stages request
metadata inside the owned run state, snapshots the admitted prompt, and calls the same
supervisor implementation. It does not invoke `agent-run` as a subprocess.

Success structured content is the T001 start response:

```json
{"format": 1, "run_id": "generated-id", "state": "running"}
```

### `agent_status`

Input:

```json
{"run_id": "generated-id"}
```

Success structured content is the unchanged T001 runtime record.

### `agent_result`

Input:

```json
{"run_id": "generated-id"}
```

Success structured content is the validated File Protocol v1 result object.

### `agent_stop`

Input:

```json
{"run_id": "generated-id"}
```

Success structured content is the T001 stop response. Stop remains idempotent and can
affect only the exact owned tmux session.

## Response and error contract

- Successful calls return the objects above as MCP structured content and a compact
  JSON text content fallback containing the same object.
- A `SupervisorError` becomes a tool result with `isError=true`. Its content is the
  existing fixed object `{"format":1,"error":{"code":"...","message":"..."}}`.
- Unexpected exceptions return only the fixed `process_failure` error. Tracebacks,
  prompt contents, environment values and backend output never enter MCP responses.
- MCP framing/validation errors are handled by the SDK and do not expose supervisor
  internals.
- Cancellation of an MCP request does not implicitly stop an already started run.
  Only `agent_stop` changes process ownership state.
- Server shutdown does not stop or reclassify runs; later CLI or MCP processes can
  inspect the file-backed state.

## Implementation constraints

- Keep the MCP adapter separate from protocol, state, tmux and backend modules.
- Refactor request validation to accept an object as well as a JSON file without
  weakening strict unknown-field checks or duplicating validation rules.
- Reuse the accepted `Supervisor` methods directly; do not parse CLI stdout and do not
  execute a shell.
- Preserve the T001 ownership marker, prompt snapshot, OS locks, atomic writes,
  redaction and fixed backend mapping.
- Do not add credential access, caller-controlled environment, executable, command,
  transport, root or state paths.
- Retain the existing `agent-run` CLI and File Protocol v1 behavior unchanged.

## Deliverables

- executable `agent-mcp` entry point;
- isolated MCP adapter/server module;
- exact pinned runtime dependency metadata;
- unit tests for tool schemas and error mapping;
- real stdio MCP client integration tests using the official SDK and real tmux;
- README installation, configuration and usage update;
- `docs/handoffs/T002-handoff.md` with exact candidate evidence.

## Exclusions

- HTTP, SSE or any network listener;
- SQLite, daemon, scheduler, retries, DAGs or automatic cleanup;
- MCP resources, prompts, sampling, elicitation or roots negotiation;
- real Codex/OpenCode adapters;
- credentials, production paths or production use;
- changes to File Protocol v1 or the frozen `agent-run` CLI;
- multiple approved roots or per-call root/state overrides;
- automatic process stop when the MCP client disconnects.

## Acceptance

- MCP initialization and `tools/list` work over stdio with exactly the four frozen
  tools and schemas above.
- A real SDK client demonstrates the complete mock lifecycle through MCP:
  `agent_start -> agent_status -> agent_result -> agent_stop`.
- A cancellation lifecycle reaches `cancelled`, and repeated stop is idempotent.
- A run started through MCP remains observable through `agent-run` after the MCP server
  exits, proving transport and process state are separate.
- Invalid fields, enums, run IDs and unsafe paths return fixed redacted tool errors.
- Tool input cannot override approved root, state root, backend executable, command or
  environment.
- Prompt replacement, duplicate-worktree locking, terminal reconciliation, unowned
  tmux isolation and state-root confinement remain covered by the T001 regression
  suite.
- Stdout contains only valid MCP traffic; planted prompt/environment/backend sentinels
  are absent from tool errors and server diagnostics.
- Ruff, formatting, compileall, all T001 tests and all T002 tests pass.

## First action after approval

Write a short T002 design note covering SDK integration, object-validation reuse,
stdio/error framing, server configuration ownership, cancellation semantics and tests;
then implement the bounded task without adding excluded capabilities.
