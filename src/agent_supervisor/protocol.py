import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .constants import (
    FORMAT,
    IDENTIFIER_PATTERN,
    MAX_PROMPT_BYTES,
    MAX_RESULT_BYTES,
    MAX_SUMMARY_BYTES,
)
from .errors import invalid, result_error, unsafe
from .paths import canonical_prompt, canonical_worktree

REQUEST_FIELDS = {
    "format",
    "project_id",
    "task_id",
    "role",
    "backend",
    "worktree",
    "prompt_file",
    "timeout_seconds",
    "expected_result",
}
RESULT_FIELDS = {"format", "run_id", "outcome", "summary", "commit", "artifact"}
ROLES = {"architect-developer"}
BACKENDS = {"mock"}
EXPECTED_RESULTS = {"handoff"}
OUTCOMES = {"succeeded", "needs_clarification", "blocked", "failed"}


def _read_json_object(path: Path, limit: int, kind: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError:
        if kind == "result":
            raise result_error("result is unavailable") from None
        raise invalid("request cannot be read") from None
    if len(raw) > limit:
        if kind == "result":
            raise result_error("result is malformed")
        raise invalid("request is too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        if kind == "result":
            raise result_error("result is malformed") from None
        raise invalid("request is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        if kind == "result":
            raise result_error("result is malformed")
        raise invalid("request must be a JSON object")
    return value


def validate_request(path: Path, approved_root: Path) -> dict[str, Any]:
    data = _read_json_object(path, MAX_RESULT_BYTES, "request")
    return validate_request_data(data, approved_root)


def validate_request_data(value: object, approved_root: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise invalid("request must be a JSON object")
    data = dict(value)
    if set(data) != REQUEST_FIELDS:
        raise invalid("request fields do not match protocol v1")
    request_format = data["format"]
    if isinstance(request_format, bool) or not isinstance(request_format, int):
        raise invalid("unsupported request format")
    if request_format != FORMAT:
        raise invalid("unsupported request format")
    for key in ("project_id", "task_id"):
        if not isinstance(data[key], str) or not re.fullmatch(IDENTIFIER_PATTERN, data[key]):
            raise invalid(f"invalid {key}")
    if not isinstance(data["role"], str) or data["role"] not in ROLES:
        raise invalid("unsupported role")
    if not isinstance(data["backend"], str) or data["backend"] not in BACKENDS:
        raise invalid("unsupported backend")
    if (
        not isinstance(data["expected_result"], str)
        or data["expected_result"] not in EXPECTED_RESULTS
    ):
        raise invalid("unsupported expected_result")
    timeout = data["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 86400:
        raise invalid("timeout_seconds must be between 1 and 86400")
    worktree = canonical_worktree(data["worktree"], approved_root)
    prompt = canonical_prompt(data["prompt_file"], worktree)
    try:
        if prompt.stat().st_size > MAX_PROMPT_BYTES:
            raise unsafe("prompt file is too large")
    except OSError:
        raise unsafe("prompt file cannot be inspected") from None
    data["worktree"] = str(worktree)
    data["prompt_file"] = str(prompt)
    return data


def snapshot_prompt(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        raise unsafe("prompt file cannot be opened safely") from None
    try:
        entry = os.fstat(fd)
        if not stat.S_ISREG(entry.st_mode) or entry.st_size > MAX_PROMPT_BYTES:
            raise unsafe("prompt file is not an admissible regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_PROMPT_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_PROMPT_BYTES:
                raise unsafe("prompt file is too large")
        return b"".join(chunks)
    except OSError:
        raise unsafe("prompt file cannot be read safely") from None
    finally:
        os.close(fd)


def validate_result(path: Path, run_id: str, worktree: Path) -> dict[str, Any]:
    data = _read_json_object(path, MAX_RESULT_BYTES, "result")
    required = {"format", "run_id", "outcome", "summary"}
    if not required.issubset(data) or not set(data).issubset(RESULT_FIELDS):
        raise result_error("result is malformed")
    if data["format"] != FORMAT or data["run_id"] != run_id:
        raise result_error("result is malformed")
    if data["outcome"] not in OUTCOMES or not isinstance(data["summary"], str):
        raise result_error("result is malformed")
    if len(data["summary"].encode("utf-8")) > MAX_SUMMARY_BYTES:
        raise result_error("result is malformed")
    commit = data.get("commit")
    if commit is not None and (
        not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None
    ):
        raise result_error("result is malformed")
    artifact = data.get("artifact")
    if artifact is not None:
        if not isinstance(artifact, str) or Path(artifact).is_absolute():
            raise result_error("result is malformed")
        candidate = worktree / artifact
        if candidate.is_symlink():
            raise result_error("result is malformed")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            raise result_error("result is malformed") from None
        if not resolved.is_relative_to(worktree) or not resolved.is_file():
            raise result_error("result is malformed")
    return data
