# T002 Implementation Review R1

Verdict: `CHANGES_REQUESTED`

Reviewed candidate: `9a91fb7600f570bf7bd1d2d4b57a69b6c18c96ba`

Reviewed handoff: `2e37c2f99abb32a6d42d8fb580dfc3a1e08347de`

Review environment: Python 3.13.9, tmux 3.4, MCP SDK 1.28.1, 2026-10-02.

## Findings

### P1: Object validation accepts JSON boolean as File Protocol format 1

`validate_request_data` compares `data["format"] != FORMAT` without first requiring an
integer that is not a boolean (`src/agent_supervisor/protocol.py`). In Python,
`True == 1`, so an MCP request containing `"format": true` passes validation and starts
a real run even though the frozen protocol requires the numeric literal `1`.

This is observable through the official SDK, not only through an internal call. The
review sent `format: true` to `agent_start`; the response was successful and returned
`state: running`.

Required closure:

- validate `format` with an exact JSON-compatible type/value check that rejects
  booleans;
- keep file-based and object-based request validation on the same rule;
- add unit and real stdio SDK tests proving `true`, `false`, strings, null, arrays and
  objects cannot start a run or create owned runtime state.

### P1: Malformed enum types bypass the invalid-request contract

The role, backend and expected-result checks perform set membership before confirming
that the supplied value is a string (`src/agent_supervisor/protocol.py`). Unhashable
JSON values such as an array or object therefore raise `TypeError`. The MCP adapter
catches that as an unexpected exception and returns `process_failure` instead of the
fixed `invalid_request` result required for invalid fields and enums.

The review reproduced this over real stdio by sending `role: []`; the returned error
was `{"code":"process_failure","message":"unexpected supervisor failure"}`.

Required closure:

- perform explicit type checks before all enum membership checks;
- classify every schema-invalid tool argument as the fixed `invalid_request` result;
- add a bounded malformed-input matrix for every start field and run-id tool,
  including unhashable JSON arrays/objects;
- assert rejected calls create no run, tmux session or worktree owner lock and do not
  disclose supplied sentinel values.

## Passing Evidence

The implementation otherwise preserves the intended bounded architecture: exactly
four stdio tools, startup-owned roots, direct Supervisor reuse, structured responses,
MCP/CLI continuity and no network or arbitrary-command interface.

```text
ruff check .                                           exit 0
ruff format --check .                                  exit 0
python3 -m compileall -q src tests                     exit 0
PYTHONPATH=src python3 -m unittest discover -v         exit 0, 29 tests
```

## Frozen R1 Closure Matrix

Only the two validation findings above block T002 R2. Do not expand T002 into new
tools, transports, adapters, scheduling, persistence, credential handling or SDK
upgrades. R2 must provide one exact implementation candidate, an updated handoff and
real stdio evidence for the malformed-input matrix while retaining all existing T001
and T002 gates.
