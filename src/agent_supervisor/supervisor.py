import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import tmux
from .constants import FORMAT, START_WAIT_SECONDS, STOP_GRACE_SECONDS, TERMINAL_STATES
from .errors import process_failure, result_error
from .protocol import validate_request, validate_result
from .state import (
    acquire_lock,
    atomic_json,
    ensure_layout,
    read_json,
    release_lock,
    run_directory,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Supervisor:
    def __init__(self, state_root: Path, source_root: Path) -> None:
        self.state_root = state_root
        self.source_root = source_root
        ensure_layout(state_root)

    def start(self, request_path: Path, approved_root: Path) -> dict[str, Any]:
        request = validate_request(request_path, approved_root)
        run_id = uuid.uuid4().hex
        run_dir = run_directory(self.state_root, run_id, must_exist=False)
        run_dir.mkdir(mode=0o700)
        lock_acquired = False
        try:
            acquire_lock(self.state_root, request["worktree"], run_id)
            lock_acquired = True
            atomic_json(run_dir / "request.json", request)
            runtime = {
                "format": FORMAT,
                "run_id": run_id,
                "state": "preparing",
                "tmux_session": tmux.session_name(run_id),
                "started_at": None,
                "finished_at": None,
                "exit_code": None,
            }
            atomic_json(run_dir / "runtime.json", runtime)
            if not tmux.start(
                runtime["tmux_session"], str(self.state_root), run_id, str(self.source_root)
            ):
                raise process_failure("failed to start owned process")
            deadline = time.monotonic() + START_WAIT_SECONDS
            while time.monotonic() < deadline:
                current = read_json(run_dir / "runtime.json")
                if current.get("state") == "running":
                    atomic_json(run_dir / "start-ack.json", {"format": FORMAT, "ready": True})
                    return {"format": FORMAT, "run_id": run_id, "state": "running"}
                if current.get("state") in TERMINAL_STATES:
                    raise process_failure("owned process failed during startup")
                time.sleep(0.05)
            raise process_failure("owned process did not become observable")
        except Exception:
            if tmux.exists(tmux.session_name(run_id)):
                tmux.kill(tmux.session_name(run_id))
            if lock_acquired:
                release_lock(self.state_root, request["worktree"], run_id)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            raise

    def _runtime(self, run_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
        run_dir = run_directory(self.state_root, run_id)
        runtime = read_json(run_dir / "runtime.json")
        request = read_json(run_dir / "request.json")
        expected_session = tmux.session_name(run_id)
        if runtime.get("run_id") != run_id or runtime.get("tmux_session") != expected_session:
            raise process_failure("supervisor state is unavailable")
        if runtime.get("state") not in TERMINAL_STATES and not tmux.exists(expected_session):
            runtime["state"] = "failed"
            runtime["finished_at"] = now()
            runtime["exit_code"] = 6
            atomic_json(run_dir / "runtime.json", runtime)
            release_lock(self.state_root, request["worktree"], run_id)
        return run_dir, runtime, request

    def status(self, run_id: str) -> dict[str, Any]:
        _run_dir, runtime, _request = self._runtime(run_id)
        return runtime

    def result(self, run_id: str) -> dict[str, Any]:
        run_dir, runtime, request = self._runtime(run_id)
        if runtime["state"] not in {"completed", "stopped"}:
            raise result_error("result is unavailable")
        return validate_result(run_dir / "result.json", run_id, Path(request["worktree"]))

    def stop(self, run_id: str) -> dict[str, Any]:
        run_dir, runtime, request = self._runtime(run_id)
        name = runtime["tmux_session"]
        state = runtime["state"]
        if state in {"preparing", "running", "draining"}:
            tmux.interrupt(name)
            deadline = time.monotonic() + STOP_GRACE_SECONDS
            while time.monotonic() < deadline and tmux.exists(name):
                time.sleep(0.05)
            if tmux.exists(name):
                tmux.kill(name)
                runtime["state"] = "cancelled"
                runtime["finished_at"] = now()
                runtime["exit_code"] = 130
                atomic_json(run_dir / "runtime.json", runtime)
                release_lock(self.state_root, request["worktree"], run_id)
            else:
                runtime = read_json(run_dir / "runtime.json")
        elif state == "completed":
            if tmux.exists(name):
                tmux.kill(name)
            runtime["state"] = "stopped"
            atomic_json(run_dir / "runtime.json", runtime)
        return {"format": FORMAT, "run_id": run_id, "state": runtime["state"]}
