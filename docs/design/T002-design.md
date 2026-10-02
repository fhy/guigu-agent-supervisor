# T002 Design Note

## SDK integration

T002 pins the official Python SDK at `mcp==1.28.1` and uses its low-level `Server`
with `stdio_server`. The low-level API is intentional: tool handlers can return an
explicit `CallToolResult`, including exact structured content and `isError=true`,
without exception text added by a higher-level wrapper. The executable exposes no
transport selector and always starts stdio.

## Module boundary

`mcp_server.py` owns MCP schemas, framing and error mapping. It receives one canonical
approved root, one owned state root, and an initialized `Supervisor`. It calls the
application object directly and never launches or parses `agent-run`.

Request JSON decoding is split from object validation in `protocol.py`. Both CLI file
requests and MCP object requests use the same strict validator. `Supervisor.start`
accepts either a validated object or the existing file path entry, with one shared run
creation path so prompt snapshots and ownership checks cannot diverge.

## Tool and error framing

The four tools have explicit JSON schemas with `additionalProperties: false`.
Successful handlers return the supervisor object as structured content plus its
compact JSON serialization as one text block. `SupervisorError` is converted to the
existing fixed protocol error object and `isError=true`; all other exceptions become
the fixed process-failure object. No traceback or exception string crosses MCP.

Supervisor operations are synchronous and may wait for tmux. Tool handlers run them
through AnyIO worker threads so the MCP event loop remains responsive. Cancelling a
tool wait does not imply `agent_stop`; process state remains controlled only by the
supervisor lifecycle.

## Configuration ownership

`agent-mcp` validates its startup arguments before any MCP bytes are written. Approved
root and state root are captured in the server object and absent from tool schemas.
The server inherits T001 state-root identity, prompt snapshot, locking, redaction and
fixed mock-backend controls. Server shutdown performs no process cleanup.

## Tests

Unit tests assert exact tool names/schemas, structured success results and redacted
error mapping. Integration tests launch `agent-mcp` through the official SDK stdio
client, list tools, run completion and cancellation lifecycles against real tmux, and
confirm CLI observation after the MCP process exits. The complete T001 suite remains a
required regression gate.
