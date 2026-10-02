import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent_supervisor.errors import invalid
from agent_supervisor.mcp_server import RUN_SCHEMA, START_SCHEMA, error_result, tools

from .helpers import ROOT, cli, output

MCP = ROOT / "agent-mcp"


def request_object(worktree: Path, prompt: Path, timeout: int = 10) -> dict[str, object]:
    return {
        "format": 1,
        "project_id": "mcp-project",
        "task_id": "T002",
        "role": "architect-developer",
        "backend": "mock",
        "worktree": str(worktree),
        "prompt_file": str(prompt),
        "timeout_seconds": timeout,
        "expected_result": "handoff",
    }


class McpSchemaTests(unittest.TestCase):
    def test_exact_tool_names_and_closed_schemas(self) -> None:
        definitions = tools()
        self.assertEqual(
            [tool.name for tool in definitions],
            ["agent_start", "agent_status", "agent_result", "agent_stop"],
        )
        self.assertEqual(definitions[0].inputSchema, START_SCHEMA)
        for tool in definitions:
            self.assertFalse(tool.inputSchema["additionalProperties"])
        for tool in definitions[1:]:
            self.assertEqual(tool.inputSchema, RUN_SCHEMA)

    def test_error_result_is_fixed_structured_and_text_content(self) -> None:
        result = error_result(invalid("fixed message"))
        expected = {
            "format": 1,
            "error": {"code": "invalid_request", "message": "fixed message"},
        }
        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent, expected)
        self.assertEqual(json.loads(result.content[0].text), expected)


class McpStdioTests(unittest.TestCase):
    def test_malformed_input_matrix_is_invalid_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            worktree = root / "worktree"
            worktree.mkdir()
            prompt = worktree / "prompt.json"
            prompt.write_text(json.dumps({"mock": {}}))
            baseline = request_object(worktree, prompt)
            sentinel = "MCP_MALFORMED_SENTINEL_31f2"
            start_cases: list[tuple[str, object]] = [
                ("format", True),
                ("format", False),
                ("format", "1"),
                ("format", None),
                ("format", []),
                ("format", {}),
                ("project_id", []),
                ("task_id", {}),
                ("role", []),
                ("role", {}),
                ("backend", []),
                ("backend", {}),
                ("worktree", []),
                ("prompt_file", {}),
                ("timeout_seconds", []),
                ("expected_result", []),
                ("expected_result", {}),
            ]
            run_id_values: list[object] = [None, True, 1, [], {}, sentinel]

            async def exercise() -> None:
                parameters = StdioServerParameters(
                    command=str(MCP),
                    args=["--approved-root", str(root), "--state-root", str(state)],
                    env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")},
                )
                async with stdio_client(parameters) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        for field, value in start_cases:
                            arguments = dict(baseline)
                            arguments[field] = value
                            result = await session.call_tool("agent_start", arguments)
                            self.assert_invalid_tool_result(result, sentinel)

                        missing = dict(baseline)
                        del missing["role"]
                        self.assert_invalid_tool_result(
                            await session.call_tool("agent_start", missing), sentinel
                        )
                        extra = dict(baseline)
                        extra["command"] = sentinel
                        self.assert_invalid_tool_result(
                            await session.call_tool("agent_start", extra), sentinel
                        )

                        for tool_name in ("agent_status", "agent_result", "agent_stop"):
                            for value in run_id_values:
                                result = await session.call_tool(tool_name, {"run_id": value})
                                self.assert_invalid_tool_result(result, sentinel)
                            result = await session.call_tool(
                                tool_name, {"run_id": "a" * 32, "state_root": sentinel}
                            )
                            self.assert_invalid_tool_result(result, sentinel)

            anyio.run(exercise)
            self.assertEqual(list((state / "runs").iterdir()), [])
            self.assertEqual(list((state / "locks").iterdir()), [])
            sessions = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
            )
            self.assertNotIn("agent-", sessions.stdout)

    def assert_invalid_tool_result(self, result: object, sentinel: str) -> None:
        self.assertTrue(result.isError)
        self.assertEqual(result.structuredContent["error"]["code"], "invalid_request")
        self.assertNotIn(sentinel, result.content[0].text)

    def test_stdio_lifecycles_and_cli_observation_after_disconnect(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            complete = root / "complete"
            cancel = root / "cancel"
            detached = root / "detached"
            for worktree in (complete, cancel, detached):
                worktree.mkdir()
            complete_prompt = complete / "prompt.json"
            complete_prompt.write_text(
                json.dumps({"mock": {"sleep_seconds": 0.2, "summary": "mcp complete"}})
            )
            cancel_prompt = cancel / "prompt.json"
            cancel_prompt.write_text(json.dumps({"mock": {"sleep_seconds": 30}}))
            detached_prompt = detached / "prompt.json"
            detached_prompt.write_text(json.dumps({"mock": {"sleep_seconds": 30}}))
            stderr_path = root / "mcp.stderr"

            async def exercise() -> str:
                parameters = StdioServerParameters(
                    command=str(MCP),
                    args=[
                        "--approved-root",
                        str(root),
                        "--state-root",
                        str(state),
                    ],
                    env={
                        "PATH": os.environ["PATH"],
                        "HOME": os.environ.get("HOME", "/tmp"),
                    },
                )
                with stderr_path.open("w", encoding="utf-8") as errlog:
                    async with stdio_client(parameters, errlog=errlog) as streams:
                        async with ClientSession(*streams) as session:
                            await session.initialize()
                            listed = await session.list_tools()
                            self.assertEqual(
                                [tool.name for tool in listed.tools],
                                ["agent_start", "agent_status", "agent_result", "agent_stop"],
                            )

                            started = await session.call_tool(
                                "agent_start", request_object(complete, complete_prompt)
                            )
                            self.assertFalse(started.isError)
                            self.assertEqual(started.structuredContent["state"], "running")
                            complete_id = started.structuredContent["run_id"]
                            while True:
                                status = await session.call_tool(
                                    "agent_status", {"run_id": complete_id}
                                )
                                if status.structuredContent["state"] == "completed":
                                    break
                                await anyio.sleep(0.05)
                            result = await session.call_tool(
                                "agent_result", {"run_id": complete_id}
                            )
                            self.assertEqual(result.structuredContent["summary"], "mcp complete")
                            stopped = await session.call_tool("agent_stop", {"run_id": complete_id})
                            self.assertEqual(stopped.structuredContent["state"], "stopped")

                            started = await session.call_tool(
                                "agent_start", request_object(cancel, cancel_prompt, timeout=60)
                            )
                            cancel_id = started.structuredContent["run_id"]
                            stopped = await session.call_tool("agent_stop", {"run_id": cancel_id})
                            self.assertEqual(stopped.structuredContent["state"], "cancelled")
                            repeated = await session.call_tool("agent_stop", {"run_id": cancel_id})
                            self.assertEqual(repeated.structuredContent["state"], "cancelled")

                            invalid_call = await session.call_tool(
                                "agent_status", {"run_id": complete_id, "state_root": "/tmp"}
                            )
                            self.assertTrue(invalid_call.isError)
                            self.assertEqual(
                                invalid_call.structuredContent["error"]["code"], "invalid_request"
                            )

                            started = await session.call_tool(
                                "agent_start", request_object(detached, detached_prompt, timeout=60)
                            )
                            return started.structuredContent["run_id"]

            detached_id = anyio.run(exercise)
            status = cli("status", detached_id, "--state-root", state)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(output(status)["state"], "running")
            stopped = cli("stop", detached_id, "--state-root", state)
            self.assertEqual(output(stopped)["state"], "cancelled")
            self.assertNotIn("Traceback", stderr_path.read_text(encoding="utf-8"))

    def test_unsafe_path_error_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw)
            state = root / "state"
            worktree = root / "worktree"
            worktree.mkdir()
            outside = Path(outside_raw) / "secret.json"
            secret = "MCP_OUTSIDE_SECRET_8d19"
            outside.write_text(secret)

            async def exercise() -> tuple[bool, dict[str, object], str]:
                parameters = StdioServerParameters(
                    command=str(MCP),
                    args=["--approved-root", str(root), "--state-root", str(state)],
                    env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")},
                )
                async with stdio_client(parameters) as streams:
                    async with ClientSession(*streams) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "agent_start", request_object(worktree, outside)
                        )
                        return (
                            bool(result.isError),
                            result.structuredContent,
                            result.content[0].text,
                        )

            is_error, structured, text = anyio.run(exercise)
            self.assertTrue(is_error)
            self.assertEqual(structured["error"]["code"], "unsafe_path_or_conflict")
            self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
