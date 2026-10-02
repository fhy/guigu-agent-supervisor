import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .constants import FORMAT, default_state_root
from .errors import SupervisorError, invalid, process_failure
from .paths import canonical_root, safe_state_root
from .supervisor import Supervisor
from .tmux import available


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise invalid("invalid command arguments")


def parser() -> argparse.ArgumentParser:
    root = Parser(prog="agent-run", add_help=True)
    commands = root.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("request")
    start.add_argument("--approved-root", required=True)
    start.add_argument("--state-root")
    for name in ("status", "stop", "result"):
        command = commands.add_parser(name)
        command.add_argument("run_id")
        command.add_argument("--state-root")
    return root


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        state_root = safe_state_root(args.state_root, default_state_root())
        if not available():
            raise process_failure("tmux is unavailable")
        source_root = Path(__file__).resolve().parents[1]
        supervisor = Supervisor(state_root, source_root)
        if args.command == "start":
            approved = canonical_root(args.approved_root)
            request = Path(args.request)
            if not request.is_absolute():
                raise invalid("request path must be absolute")
            response = supervisor.start(request, approved)
        elif args.command == "status":
            response = supervisor.status(args.run_id)
        elif args.command == "stop":
            response = supervisor.stop(args.run_id)
        else:
            response = supervisor.result(args.run_id)
        emit(response)
        return 0
    except SupervisorError as error:
        emit({"format": FORMAT, "error": {"code": error.code, "message": error.message}})
        print(error.message, file=sys.stderr)
        return error.exit_code
    except Exception:
        error = process_failure("unexpected supervisor failure")
        emit({"format": FORMAT, "error": {"code": error.code, "message": error.message}})
        print(error.message, file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
