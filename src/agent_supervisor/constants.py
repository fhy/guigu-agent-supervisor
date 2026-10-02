import os
from pathlib import Path

FORMAT = 1
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
RUN_ID_PATTERN = r"^[0-9a-f]{32}$"
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled", "stopped"})
ACTIVE_STATES = frozenset({"requested", "preparing", "running", "draining"})
MAX_PROMPT_BYTES = 1024 * 1024
MAX_RESULT_BYTES = 16 * 1024
MAX_SUMMARY_BYTES = 4096
MAX_LOG_BYTES = 256 * 1024
START_WAIT_SECONDS = 8.0
STOP_GRACE_SECONDS = 3.0
SAFE_WORKER_ENV = frozenset({"LANG", "LC_ALL", "TZ"})


def default_state_root() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "guigu-agent-supervisor"
    return Path.home() / ".local" / "state" / "guigu-agent-supervisor"
