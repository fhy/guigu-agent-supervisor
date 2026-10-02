import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .constants import FORMAT, RUN_ID_PATTERN
from .errors import not_found, process_failure, unsafe


def ensure_layout(root: Path) -> None:
    for name in ("runs", "locks"):
        (root / name).mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(root / name, 0o700)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise process_failure("supervisor state is unavailable") from None
    if not isinstance(data, dict):
        raise process_failure("supervisor state is unavailable")
    return data


def run_directory(root: Path, run_id: str, must_exist: bool = True) -> Path:
    import re

    if re.fullmatch(RUN_ID_PATTERN, run_id) is None:
        raise not_found()
    path = root / "runs" / run_id
    if must_exist and not path.is_dir():
        raise not_found()
    return path


def lock_path(root: Path, worktree: str) -> Path:
    digest = hashlib.sha256(worktree.encode("utf-8")).hexdigest()
    return root / "locks" / f"{digest}.lock"


def acquire_lock(root: Path, worktree: str, run_id: str) -> Path:
    path = lock_path(root, worktree)
    payload = json.dumps({"format": FORMAT, "run_id": run_id, "worktree": worktree}) + "\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise unsafe("worktree already has an active run") from None
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


def release_lock(root: Path, worktree: str, run_id: str) -> None:
    path = lock_path(root, worktree)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if data.get("run_id") == run_id and data.get("worktree") == worktree:
        path.unlink(missing_ok=True)
