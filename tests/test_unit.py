import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_supervisor.constants import FORMAT
from agent_supervisor.errors import SupervisorError
from agent_supervisor.paths import canonical_prompt, safe_state_root
from agent_supervisor.protocol import validate_request, validate_result
from agent_supervisor.state import (
    acquire_lock,
    atomic_json,
    ensure_layout,
    lock_path,
    read_json,
    release_lock,
    run_guard,
    worktree_guard,
)
from agent_supervisor.supervisor import Supervisor

from .helpers import write_request


class ProtocolTests(unittest.TestCase):
    def test_valid_request_is_canonicalized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            request, worktree = write_request(root)
            value = validate_request(request, root.resolve())
            self.assertEqual(value["worktree"], str(worktree.resolve()))

    def test_unknown_request_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            request, _ = write_request(root)
            data = json.loads(request.read_text())
            data["command"] = "touch /tmp/not-allowed"
            request.write_text(json.dumps(data))
            with self.assertRaises(SupervisorError) as caught:
                validate_request(request, root.resolve())
            self.assertEqual(caught.exception.exit_code, 2)

    def test_unknown_enums_and_relative_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            request, _ = write_request(root)
            baseline = json.loads(request.read_text())
            cases = [
                ("backend", "shell"),
                ("role", "operator"),
                ("expected_result", "anything"),
                ("worktree", "relative"),
                ("prompt_file", "relative"),
            ]
            for field, value in cases:
                with self.subTest(field=field):
                    data = dict(baseline)
                    data[field] = value
                    request.write_text(json.dumps(data))
                    with self.assertRaises(SupervisorError):
                        validate_request(request, root.resolve())

    def test_worktree_outside_root_and_large_prompt_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw)
            outside = Path(outside_raw)
            request, _ = write_request(outside)
            with self.assertRaises(SupervisorError):
                validate_request(request, root.resolve())

            request, _ = write_request(root)
            data = json.loads(request.read_text())
            Path(data["prompt_file"]).write_bytes(b"x" * (1024 * 1024 + 1))
            with self.assertRaises(SupervisorError):
                validate_request(request, root.resolve())

    def test_prompt_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "target"
            target.write_text("secret")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaises(SupervisorError):
                canonical_prompt(str(link), root.resolve())

    def test_result_artifact_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            result = root / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "format": 1,
                        "run_id": "a" * 32,
                        "outcome": "succeeded",
                        "summary": "ok",
                        "artifact": "../outside",
                    }
                )
            )
            with self.assertRaises(SupervisorError):
                validate_result(result, "a" * 32, root)


class StateTests(unittest.TestCase):
    def test_atomic_file_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "state.json"
            atomic_json(path, {"format": 1})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_exclusive_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "locks").mkdir()
            acquire_lock(root, "/worktree", "a" * 32)
            with self.assertRaises(SupervisorError) as caught:
                acquire_lock(root, "/worktree", "b" * 32)
            self.assertEqual(caught.exception.exit_code, 3)

    def test_terminal_publication_wins_before_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = safe_state_root(str(root / "state"), root / "unused")
            ensure_layout(state)
            run_id = "a" * 32
            run_dir = state / "runs" / run_id
            run_dir.mkdir(mode=0o700)
            worktree = str(root / "worktree")
            Path(worktree).mkdir()
            runtime = {
                "format": FORMAT,
                "run_id": run_id,
                "state": "running",
                "tmux_session": f"agent-{run_id}",
                "started_at": "2026-10-02T00:00:00Z",
                "finished_at": None,
                "exit_code": None,
            }
            atomic_json(run_dir / "runtime.json", runtime)
            atomic_json(run_dir / "request.json", {"worktree": worktree})
            supervisor = Supervisor(state, root)
            result: list[dict[str, object]] = []

            with run_guard(run_dir):
                thread = threading.Thread(target=lambda: result.append(supervisor.status(run_id)))
                with patch("agent_supervisor.supervisor.tmux.exists", return_value=False):
                    thread.start()
                    runtime["state"] = "completed"
                    runtime["finished_at"] = "2026-10-02T00:00:01Z"
                    runtime["exit_code"] = 0
                    atomic_json(run_dir / "runtime.json", runtime)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result[0]["state"], "completed")
            self.assertEqual(read_json(run_dir / "runtime.json")["state"], "completed")

    def test_terminal_publication_is_preserved_when_stop_was_queued(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = safe_state_root(str(root / "state"), root / "unused")
            ensure_layout(state)
            run_id = "a" * 32
            run_dir = state / "runs" / run_id
            run_dir.mkdir(mode=0o700)
            worktree = str(root / "worktree")
            Path(worktree).mkdir()
            runtime = {
                "format": FORMAT,
                "run_id": run_id,
                "state": "running",
                "tmux_session": f"agent-{run_id}",
                "started_at": "2026-10-02T00:00:00Z",
                "finished_at": None,
                "exit_code": None,
            }
            atomic_json(run_dir / "runtime.json", runtime)
            atomic_json(run_dir / "request.json", {"worktree": worktree})
            supervisor = Supervisor(state, root)
            result: list[dict[str, object]] = []
            started = threading.Event()

            def stop() -> None:
                started.set()
                result.append(supervisor.stop(run_id))

            with patch("agent_supervisor.supervisor.tmux.exists", return_value=False):
                with run_guard(run_dir):
                    thread = threading.Thread(target=stop)
                    thread.start()
                    self.assertTrue(started.wait(timeout=1))
                    runtime["state"] = "completed"
                    runtime["finished_at"] = "2026-10-02T00:00:01Z"
                    runtime["exit_code"] = 0
                    atomic_json(run_dir / "runtime.json", runtime)
                thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result[0]["state"], "stopped")
            self.assertEqual(read_json(run_dir / "runtime.json")["state"], "stopped")

    def test_queued_old_release_preserves_replacement_owner(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = safe_state_root(str(root / "state"), root / "unused")
            ensure_layout(state)
            worktree = "/canonical/worktree"
            old_run = "a" * 32
            new_run = "b" * 32
            acquire_lock(state, worktree, old_run)
            started = threading.Event()

            def old_release() -> None:
                started.set()
                release_lock(state, worktree, old_run)

            with worktree_guard(state, worktree):
                thread = threading.Thread(target=old_release)
                thread.start()
                self.assertTrue(started.wait(timeout=1))
                owner = lock_path(state, worktree)
                owner.unlink()
                fd = os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump({"format": FORMAT, "run_id": new_run, "worktree": worktree}, handle)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(read_json(lock_path(state, worktree))["run_id"], new_run)


if __name__ == "__main__":
    unittest.main()
