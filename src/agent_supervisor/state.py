import contextlib
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from .constants import FORMAT, RUN_ID_PATTERN
from .errors import not_found, process_failure, unsafe


def ensure_layout(root: Path) -> None:
    for name in ("runs", "locks"):
        path = root / name
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        try:
            entry = path.lstat()
        except OSError:
            raise unsafe("state layout is unavailable") from None
        if not stat.S_ISDIR(entry.st_mode) or stat.S_IMODE(entry.st_mode) != 0o700:
            raise unsafe("state layout must contain mode 0700 directories")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    _require_private_directory(path.parent)
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


def atomic_bytes(path: Path, value: bytes) -> None:
    _require_private_directory(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
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


def _require_private_directory(path: Path) -> None:
    try:
        entry = path.lstat()
    except OSError:
        raise process_failure("supervisor state is unavailable") from None
    if not stat.S_ISDIR(entry.st_mode) or stat.S_IMODE(entry.st_mode) != 0o700:
        raise process_failure("supervisor state is unavailable")


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


@contextlib.contextmanager
def file_guard(path: Path):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError:
        raise process_failure("supervisor lock is unavailable") from None
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def run_guard(run_dir: Path):
    return file_guard(run_dir / ".runtime.guard")


def lock_path(root: Path, worktree: str) -> Path:
    digest = hashlib.sha256(worktree.encode("utf-8")).hexdigest()
    return root / "locks" / f"{digest}.lock"


def worktree_guard(root: Path, worktree: str):
    digest = hashlib.sha256(worktree.encode("utf-8")).hexdigest()
    return file_guard(root / "locks" / f"{digest}.guard")


def acquire_lock(root: Path, worktree: str, run_id: str) -> Path:
    path = lock_path(root, worktree)
    payload = json.dumps({"format": FORMAT, "run_id": run_id, "worktree": worktree}) + "\n"
    with worktree_guard(root, worktree):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            raise unsafe("worktree already has an active run") from None
        except OSError:
            raise unsafe("worktree lock is unavailable") from None
        try:
            os.write(fd, payload.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
    return path


def release_lock(root: Path, worktree: str, run_id: str) -> None:
    path = lock_path(root, worktree)
    with worktree_guard(root, worktree):
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except FileNotFoundError:
            return
        except OSError:
            return
        try:
            descriptor_stat = os.fstat(fd)
            try:
                raw = os.read(fd, 4096)
                data = json.loads(raw.decode("utf-8"))
                path_stat = path.lstat()
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return
            owned = data.get("run_id") == run_id and data.get("worktree") == worktree
            same_object = (descriptor_stat.st_dev, descriptor_stat.st_ino) == (
                path_stat.st_dev,
                path_stat.st_ino,
            )
            if owned and same_object and stat.S_ISREG(path_stat.st_mode):
                path.unlink()
        finally:
            os.close(fd)
