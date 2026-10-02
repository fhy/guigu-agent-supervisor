import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from .helpers import cli, output, wait_state, write_request


class ProcessTests(unittest.TestCase):
    def test_complete_result_and_stop_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"summary": "done"}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = output(started)["run_id"]
            wait_state(state, run_id, {"completed"})
            result = cli("result", run_id, "--state-root", state)
            self.assertEqual(output(result)["summary"], "done")
            stopped = cli("stop", run_id, "--state-root", state)
            self.assertEqual(output(stopped)["state"], "stopped")
            repeated = cli("stop", run_id, "--state-root", state)
            self.assertEqual(output(repeated)["state"], "stopped")

    def test_immediate_completion_and_bounded_logs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"sleep_seconds": 0, "log_bytes": 300000}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = output(started)["run_id"]
            wait_state(state, run_id, {"completed"})
            log = json.loads((state / "runs" / run_id / "backend-log.json").read_text())
            self.assertTrue(log["truncated"])
            self.assertLessEqual(len(log["stdout"].encode()), 256 * 1024)
            self.assertLessEqual(len(log["stderr"].encode()), 256 * 1024)

    def test_cancel_and_duplicate_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"sleep_seconds": 30}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            run_id = output(started)["run_id"]
            duplicate = cli("start", request, "--approved-root", root, "--state-root", state)
            self.assertEqual(duplicate.returncode, 3)
            before = time.monotonic()
            stopped = cli("stop", run_id, "--state-root", state)
            self.assertEqual(output(stopped)["state"], "cancelled")
            self.assertLess(time.monotonic() - before, 2.0)

    def test_forced_stop_fallback_removes_owned_session(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"sleep_seconds": 30}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            run_id = output(started)["run_id"]
            session = f"agent-{run_id}"
            subprocess.run(
                [
                    "tmux",
                    "set-option",
                    "-w",
                    "-t",
                    f"={session}:0",
                    "remain-on-exit",
                    "on",
                ],
                check=True,
            )
            stopped = cli("stop", run_id, "--state-root", state)
            self.assertEqual(output(stopped)["state"], "cancelled")
            alive = subprocess.run(
                ["tmux", "has-session", "-t", f"={session}"], capture_output=True
            )
            self.assertNotEqual(alive.returncode, 0)

    def test_timeout_and_malformed_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"sleep_seconds": 3}}, timeout=1)
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            timed_out = wait_state(state, output(started)["run_id"], {"failed"})
            self.assertEqual(timed_out["exit_code"], 124)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"result_mode": "malformed"}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            run_id = output(started)["run_id"]
            wait_state(state, run_id, {"failed"})
            result = cli("result", run_id, "--state-root", state)
            self.assertEqual(result.returncode, 7)

    def test_unowned_tmux_session_is_untouched(self) -> None:
        name = "t001-unowned-session"
        subprocess.run(["tmux", "kill-session", "-t", f"={name}"], capture_output=True)
        subprocess.run(["tmux", "new-session", "-d", "-s", name, "sleep 30"], check=True)
        try:
            with tempfile.TemporaryDirectory() as raw:
                result = cli("stop", "f" * 32, "--state-root", Path(raw) / "state")
                self.assertEqual(result.returncode, 4)
                alive = subprocess.run(
                    ["tmux", "has-session", "-t", f"={name}"], capture_output=True
                )
                self.assertEqual(alive.returncode, 0)
        finally:
            subprocess.run(["tmux", "kill-session", "-t", f"={name}"], capture_output=True)

    def test_shell_metacharacters_are_data(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            marker = root / "executed"
            state = root / "state"
            request, _ = write_request(
                root, {"mock": {"summary": f"$(touch {marker}) ; `touch {marker}`"}}
            )
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            run_id = output(started)["run_id"]
            wait_state(state, run_id, {"completed"})
            self.assertFalse(marker.exists())

    def test_different_worktrees_run_independently(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            first, _ = write_request(first_dir, {"mock": {"sleep_seconds": 2}})
            second, _ = write_request(second_dir, {"mock": {"sleep_seconds": 2}})
            one = cli("start", first, "--approved-root", root, "--state-root", state)
            two = cli("start", second, "--approved-root", root, "--state-root", state)
            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertEqual(two.returncode, 0, two.stderr)
            one_id = output(one)["run_id"]
            two_id = output(two)["run_id"]
            self.assertNotEqual(one_id, two_id)
            cli("stop", one_id, "--state-root", state)
            cli("stop", two_id, "--state-root", state)

    def test_stale_tmux_is_failed_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(root, {"mock": {"sleep_seconds": 30}})
            started = cli("start", request, "--approved-root", root, "--state-root", state)
            run_id = output(started)["run_id"]
            subprocess.run(["tmux", "kill-session", "-t", f"=agent-{run_id}"], check=True)
            status = cli("status", run_id, "--state-root", state)
            self.assertEqual(output(status)["state"], "failed")
            restarted = cli("start", request, "--approved-root", root, "--state-root", state)
            self.assertEqual(restarted.returncode, 0, restarted.stderr)
            cli("stop", output(restarted)["run_id"], "--state-root", state)

    def test_errors_redact_prompt_and_environment(self) -> None:
        sentinel = "T001_ENV_SENTINEL_91d7"
        prompt_secret = "T001_PROMPT_SECRET_a21c"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            state = root / "state"
            request, _ = write_request(
                root,
                {"mock": {"summary": prompt_secret, "result_mode": "missing"}},
            )
            environment = os.environ.copy()
            environment["AWS_SECRET_ACCESS_KEY"] = sentinel
            started = subprocess.run(
                [
                    str(Path(__file__).resolve().parents[1] / "agent-run"),
                    "start",
                    str(request),
                    "--approved-root",
                    str(root),
                    "--state-root",
                    str(state),
                ],
                capture_output=True,
                text=True,
                env=environment,
                timeout=15,
            )
            run_id = output(started)["run_id"]
            wait_state(state, run_id, {"failed"})
            result = cli("result", run_id, "--state-root", state)
            combined = result.stdout + result.stderr
            self.assertNotIn(sentinel, combined)
            self.assertNotIn(prompt_secret, combined)
            run_dir = state / "runs" / run_id
            self.assertEqual(run_dir.stat().st_mode & 0o777, 0o700)
            for path in run_dir.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
