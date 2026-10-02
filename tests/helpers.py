import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "agent-run"


def write_request(
    directory: Path, prompt_data: object | None = None, timeout: int = 10
) -> tuple[Path, Path]:
    worktree = directory / "worktree"
    worktree.mkdir(parents=True)
    prompt = worktree / "prompt.json"
    prompt.write_text(json.dumps(prompt_data or {"mock": {}}), encoding="utf-8")
    request = directory / "request.json"
    request.write_text(
        json.dumps(
            {
                "format": 1,
                "project_id": "test-project",
                "task_id": "T001",
                "role": "architect-developer",
                "backend": "mock",
                "worktree": str(worktree),
                "prompt_file": str(prompt),
                "timeout_seconds": timeout,
                "expected_result": "handoff",
            }
        ),
        encoding="utf-8",
    )
    return request, worktree


def cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(CLI), *(str(arg) for arg in args)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp")},
    )


def output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return json.loads(result.stdout)


def wait_state(
    state_root: Path, run_id: str, states: set[str], timeout: float = 8
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        result = cli("status", run_id, "--state-root", state_root)
        latest = output(result)
        if latest.get("state") in states:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"state did not reach {states}: {latest}")
