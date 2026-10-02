import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from ..constants import FORMAT
from ..state import atomic_json


def _directives(prompt: Path) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "sleep_seconds": 0.2,
        "outcome": "succeeded",
        "summary": "mock completed",
        "result_mode": "valid",
        "exit_code": 0,
        "log_bytes": 0,
    }
    try:
        parsed = json.loads(prompt.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return defaults
    if isinstance(parsed, dict) and isinstance(parsed.get("mock"), dict):
        mock = parsed["mock"]
        if isinstance(mock.get("sleep_seconds"), (int, float)):
            defaults["sleep_seconds"] = max(0.0, min(float(mock["sleep_seconds"]), 86400.0))
        if mock.get("outcome") in {"succeeded", "needs_clarification", "blocked", "failed"}:
            defaults["outcome"] = mock["outcome"]
        if isinstance(mock.get("summary"), str):
            defaults["summary"] = mock["summary"]
        if mock.get("result_mode") in {"valid", "missing", "malformed"}:
            defaults["result_mode"] = mock["result_mode"]
        if isinstance(mock.get("exit_code"), int) and 0 <= mock["exit_code"] <= 255:
            defaults["exit_code"] = mock["exit_code"]
        if isinstance(mock.get("log_bytes"), int):
            defaults["log_bytes"] = max(0, min(mock["log_bytes"], 1024 * 1024))
    return defaults


def run(prompt: Path, result_path: Path, run_id: str) -> int:
    directives = _directives(prompt)
    if directives["log_bytes"]:
        print("o" * directives["log_bytes"])
        print("e" * directives["log_bytes"], file=sys.stderr)
    time.sleep(directives["sleep_seconds"])
    mode = directives["result_mode"]
    if mode == "malformed":
        fd = os.open(result_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("{malformed\n")
    elif mode == "valid":
        atomic_json(
            result_path,
            {
                "format": FORMAT,
                "run_id": run_id,
                "outcome": directives["outcome"],
                "summary": directives["summary"],
            },
        )
    return directives["exit_code"]
