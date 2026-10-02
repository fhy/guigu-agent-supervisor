import os
import signal
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from .backends.mock import run as run_mock
from .constants import MAX_LOG_BYTES, SAFE_WORKER_ENV, START_WAIT_SECONDS
from .errors import SupervisorError
from .protocol import validate_result
from .state import atomic_json, read_json, release_lock, run_directory


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BoundedCapture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.content = bytearray()
        self.truncated = False

    def write(self, value: str) -> int:
        encoded = value.encode("utf-8", errors="replace")
        remaining = self.limit - len(self.content)
        if remaining > 0:
            self.content.extend(encoded[:remaining])
        if len(encoded) > remaining:
            self.truncated = True
        return len(value)

    def flush(self) -> None:
        pass

    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def main() -> int:
    root_value = os.environ.get("AGENT_SUPERVISOR_STATE_ROOT")
    run_id = os.environ.get("AGENT_SUPERVISOR_RUN_ID")
    if not root_value or not run_id:
        return 6
    retained_environment = {
        key: value for key, value in os.environ.items() if key in SAFE_WORKER_ENV
    }
    os.environ.clear()
    os.environ.update(retained_environment)
    root = Path(root_value)
    run_dir = run_directory(root, run_id)
    request = read_json(run_dir / "request.json")
    runtime_path = run_dir / "runtime.json"
    runtime = read_json(runtime_path)
    atomic_json(run_dir / "backend-log.json", {"stdout": "", "stderr": "", "truncated": False})
    cancelled = False

    def handle_signal(_signum: int, _frame: object) -> None:
        nonlocal cancelled
        cancelled = True
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    runtime["state"] = "running"
    runtime["started_at"] = now()
    atomic_json(runtime_path, runtime)
    ack_deadline = time.monotonic() + START_WAIT_SECONDS
    while not (run_dir / "start-ack.json").is_file():
        if time.monotonic() >= ack_deadline:
            runtime["state"] = "failed"
            runtime["finished_at"] = now()
            runtime["exit_code"] = 6
            atomic_json(runtime_path, runtime)
            release_lock(root, request["worktree"], run_id)
            return 6
        time.sleep(0.02)
    exit_code: int | None = None
    stdout = BoundedCapture(MAX_LOG_BYTES)
    stderr = BoundedCapture(MAX_LOG_BYTES)
    try:
        signal.setitimer(signal.ITIMER_REAL, request["timeout_seconds"])

        def timeout_signal(_signum: int, _frame: object) -> None:
            raise TimeoutError

        signal.signal(signal.SIGALRM, timeout_signal)
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = run_mock(Path(request["prompt_file"]), run_dir / "result.json", run_id)
        signal.setitimer(signal.ITIMER_REAL, 0)
        if exit_code != 0:
            runtime["state"] = "failed"
        else:
            try:
                validate_result(run_dir / "result.json", run_id, Path(request["worktree"]))
                runtime["state"] = "completed"
            except SupervisorError:
                runtime["state"] = "failed"
                exit_code = 7
    except TimeoutError:
        runtime["state"] = "failed"
        exit_code = 124
    except KeyboardInterrupt:
        runtime["state"] = "cancelled"
        exit_code = 130
    except Exception:
        runtime["state"] = "cancelled" if cancelled else "failed"
        exit_code = 130 if cancelled else 6
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        runtime["finished_at"] = now()
        runtime["exit_code"] = exit_code
        atomic_json(
            run_dir / "backend-log.json",
            {
                "stdout": stdout.text(),
                "stderr": stderr.text(),
                "truncated": stdout.truncated or stderr.truncated,
            },
        )
        atomic_json(runtime_path, runtime)
        release_lock(root, request["worktree"], run_id)
    return exit_code or 0


if __name__ == "__main__":
    raise SystemExit(main())
