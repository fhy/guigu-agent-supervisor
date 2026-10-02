import json
import os
import stat
from pathlib import Path

from .constants import STATE_ROOT_MARKER
from .errors import SupervisorError, invalid, unsafe


def canonical_root(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise invalid("approved root must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise unsafe("approved root does not exist") from None
    if not resolved.is_dir():
        raise unsafe("approved root must be a directory")
    return resolved


def canonical_worktree(value: object, approved_root: Path) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise invalid("worktree must be an absolute path")
    try:
        resolved = Path(value).resolve(strict=True)
    except OSError:
        raise unsafe("worktree does not exist") from None
    if not resolved.is_dir() or not resolved.is_relative_to(approved_root):
        raise unsafe("worktree is outside the approved root")
    return resolved


def canonical_prompt(value: object, worktree: Path) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise invalid("prompt_file must be an absolute path")
    original = Path(value)
    if original.is_symlink():
        raise unsafe("prompt file must not be a symlink")
    try:
        resolved = original.resolve(strict=True)
    except OSError:
        raise unsafe("prompt file does not exist") from None
    if not resolved.is_relative_to(worktree):
        raise unsafe("prompt file is outside the worktree")
    if not resolved.is_file() or resolved.is_symlink():
        raise unsafe("prompt file must be a regular non-symlink file")
    return resolved


def safe_state_root(value: str | None, default: Path) -> Path:
    path = Path(value) if value else default
    if not path.is_absolute():
        raise invalid("state root must be absolute")
    path = Path(os.path.abspath(path))
    _reject_symlink_ancestors(path)
    created = False
    try:
        path.mkdir(mode=0o700, parents=True)
        created = True
        path.chmod(0o700)
    except FileExistsError:
        pass
    _reject_symlink_ancestors(path)
    try:
        root_stat = path.lstat()
    except OSError:
        raise unsafe("state root is unavailable") from None
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_IMODE(root_stat.st_mode) != 0o700:
        raise unsafe("state root must be a mode 0700 directory")

    marker = path / ".supervisor-root.json"
    if created:
        _create_marker(marker)
    else:
        _validate_marker(marker)
    return path


def _reject_symlink_ancestors(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            entry = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise unsafe("state root ancestry is unavailable") from None
        if stat.S_ISLNK(entry.st_mode):
            raise unsafe("state root must not traverse symlinks")


def _create_marker(path: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(STATE_ROOT_MARKER, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        raise unsafe("state root ownership marker cannot be created") from None


def _validate_marker(path: Path) -> None:
    try:
        marker_stat = path.lstat()
        if not stat.S_ISREG(marker_stat.st_mode) or stat.S_IMODE(marker_stat.st_mode) != 0o600:
            raise unsafe("state root ownership marker is invalid")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except SupervisorError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise unsafe("state root ownership marker is invalid") from None
    if value != STATE_ROOT_MARKER:
        raise unsafe("state root ownership marker is invalid")
