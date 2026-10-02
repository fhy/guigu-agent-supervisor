# T002 Implementation Handoff

## Candidate

- Implementation candidate: `9a91fb7600f570bf7bd1d2d4b57a69b6c18c96ba`
- Specification commit: `474d4118adb287ce3785d7d4c48c49648dbf01fe`
- Accepted T001 baseline: `f4d4a943e4436cd59633b860b4a4f41aa31c220f`
- Status: ready for independent review; not yet accepted
- Remote writes after T002 started: none

## Delivered

- Executable `agent-mcp` with fixed startup-only approved root and state root.
- Official Python MCP SDK pinned to `mcp==1.28.1`.
- Stdio-only low-level MCP server with exactly `agent_start`, `agent_status`,
  `agent_result`, and `agent_stop`.
- Closed tool schemas and strict manual validation producing fixed redacted tool errors.
- Structured MCP content plus compact JSON text fallback for every tool response.
- Shared object/file request validation and one Supervisor start implementation.
- Direct Supervisor calls through AnyIO worker threads; no CLI parsing or shell use.
- Official SDK client tests using real stdio, tmux and cross-interface CLI observation.
- README installation and startup documentation.

## Automated evidence

Run on 2026-10-02 with Python 3.13.9, tmux 3.4 and MCP SDK 1.28.1:

```text
ruff check .
All checks passed!

ruff format --check .
18 files already formatted

python3 -m compileall -q src tests
(no output)

PYTHONPATH=src python3 -m unittest discover -v
Ran 29 tests in 10.332s
OK

focused T001 race suite, five consecutive runs
Ran 3 tests each iteration
OK

git diff --check
(no output)
```

The 29 tests comprise the accepted 25-test T001 suite plus four T002 tests. T002 tests
verify exact schemas, structured/redacted errors, unsafe-path redaction, real SDK
initialization and tool discovery, completed and cancelled lifecycles, idempotent stop,
and CLI observation of a run after the MCP server disconnects. No tmux session remained
after cleanup.

## Fresh-shell evidence

Executed the official SDK integration test from `bash --noprofile --norc`:

```text
test_stdio_lifecycles_and_cli_observation_after_disconnect ... ok
Ran 1 test in 1.144s
OK
```

That test launches `agent-mcp` as a real stdio subprocess, verifies exactly four tools,
runs completion/result/stop and cancellation/idempotent-stop paths, exits the MCP
server while another run remains active, observes that run through `agent-run`, and
then stops it through the CLI.

## Security boundary

- MCP callers cannot select a transport, approved root, state root, executable,
  command, environment or backend adapter implementation.
- Tool errors contain only fixed protocol codes/messages and never tracebacks, prompt
  contents, environment values or backend output.
- T001 state-root ownership, atomic prompt snapshot, runtime/worktree locks, exact tmux
  ownership and bounded logs remain unchanged and covered by regression tests.
- MCP disconnect and request cancellation do not implicitly alter Agent process state.

## Limitations

- The wrapper is local stdio only and uses only the deterministic mock backend.
- The SDK is intentionally pinned to 1.28.1; MCP SDK 2.x migration is not included.
- There are no MCP resources, prompts, sampling, elicitation or roots negotiation.
- There is no network listener, daemon, scheduling, retry, persistence migration,
  credential injection or production support.

## Review request

Independently review exact commit `9a91fb7600f570bf7bd1d2d4b57a69b6c18c96ba`, rerun
all checks above, and repeat the stdio lifecycle from a fresh shell. Keep T002 in
`review` until the exact candidate is accepted. Do not push or begin an SDK upgrade or
new supervisor capability as part of T002 review.
