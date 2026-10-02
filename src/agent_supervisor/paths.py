from pathlib import Path

from .errors import invalid, unsafe


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
    if path.is_symlink():
        raise unsafe("state root must not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise unsafe("state root must be a directory")
    os_mode = resolved.stat().st_mode & 0o777
    if os_mode & 0o077:
        resolved.chmod(0o700)
    return resolved
