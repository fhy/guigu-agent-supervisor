import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .constants import FORMAT, default_state_root
from .errors import SupervisorError, invalid, process_failure
from .paths import canonical_root, safe_state_root
from .supervisor import Supervisor
from .tmux import available

IDENTIFIER_SCHEMA = {
    "type": "string",
    "pattern": r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
}
START_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "format": {"const": FORMAT},
        "project_id": IDENTIFIER_SCHEMA,
        "task_id": IDENTIFIER_SCHEMA,
        "role": {"type": "string", "enum": ["architect-developer"]},
        "backend": {"type": "string", "enum": ["mock"]},
        "worktree": {"type": "string"},
        "prompt_file": {"type": "string"},
        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
        "expected_result": {"type": "string", "enum": ["handoff"]},
    },
    "required": [
        "format",
        "project_id",
        "task_id",
        "role",
        "backend",
        "worktree",
        "prompt_file",
        "timeout_seconds",
        "expected_result",
    ],
    "additionalProperties": False,
}
RUN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"run_id": {"type": "string", "pattern": r"^[0-9a-f]{32}$"}},
    "required": ["run_id"],
    "additionalProperties": False,
}


def tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="agent_start",
            description="Start one bounded agent run using File Protocol v1.",
            inputSchema=START_SCHEMA,
        ),
        types.Tool(
            name="agent_status",
            description="Return supervisor runtime facts for one run.",
            inputSchema=RUN_SCHEMA,
        ),
        types.Tool(
            name="agent_result",
            description="Return the validated structured result for one completed run.",
            inputSchema=RUN_SCHEMA,
        ),
        types.Tool(
            name="agent_stop",
            description="Stop only the exact supervisor-owned run.",
            inputSchema=RUN_SCHEMA,
        ),
    ]


def tool_result(value: dict[str, Any], *, is_error: bool = False) -> types.CallToolResult:
    compact = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=compact)],
        structuredContent=value,
        isError=is_error,
    )


def error_result(error: SupervisorError) -> types.CallToolResult:
    return tool_result(
        {"format": FORMAT, "error": {"code": error.code, "message": error.message}},
        is_error=True,
    )


def _run_id(arguments: dict[str, Any]) -> str:
    run_id = arguments.get("run_id")
    if (
        set(arguments) != {"run_id"}
        or not isinstance(run_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", run_id) is None
    ):
        raise invalid("invalid tool arguments")
    return run_id


def create_server(supervisor: Supervisor, approved_root: Path) -> Server:
    server = Server("guigu-agent-supervisor", version="0.1.0")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tools()

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        try:
            if not isinstance(arguments, dict):
                raise invalid("invalid tool arguments")
            if name == "agent_start":
                response = await anyio.to_thread.run_sync(
                    supervisor.start_request, arguments, approved_root
                )
            elif name == "agent_status":
                response = await anyio.to_thread.run_sync(supervisor.status, _run_id(arguments))
            elif name == "agent_result":
                response = await anyio.to_thread.run_sync(supervisor.result, _run_id(arguments))
            elif name == "agent_stop":
                response = await anyio.to_thread.run_sync(supervisor.stop, _run_id(arguments))
            else:
                raise invalid("unknown tool")
            return tool_result(response)
        except SupervisorError as error:
            return error_result(error)
        except Exception:
            return error_result(process_failure("unexpected supervisor failure"))

    return server


async def run_stdio(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="agent-mcp")
    value.add_argument("--approved-root", required=True)
    value.add_argument("--state-root")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        approved_root = canonical_root(args.approved_root)
        state_root = safe_state_root(args.state_root, default_state_root())
        if not available():
            raise process_failure("tmux is unavailable")
        source_root = Path(__file__).resolve().parents[1]
        server = create_server(Supervisor(state_root, source_root), approved_root)
        anyio.run(run_stdio, server)
        return 0
    except SupervisorError as error:
        print(error.message, file=sys.stderr)
        return error.exit_code
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("unexpected supervisor failure", file=sys.stderr)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
