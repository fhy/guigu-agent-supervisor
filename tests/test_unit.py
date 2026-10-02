import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_supervisor.errors import SupervisorError
from agent_supervisor.paths import canonical_prompt
from agent_supervisor.protocol import validate_request, validate_result
from agent_supervisor.state import acquire_lock, atomic_json

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


if __name__ == "__main__":
    unittest.main()
