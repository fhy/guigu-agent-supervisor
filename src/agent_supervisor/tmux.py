import subprocess


def _tmux(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tmux", *args],
        check=check,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def session_name(run_id: str) -> str:
    return f"agent-{run_id}"


def exists(name: str) -> bool:
    return _tmux(["has-session", "-t", f"={name}"]).returncode == 0


def start(name: str, state_root: str, run_id: str, source_root: str) -> bool:
    env = [
        "-e",
        f"AGENT_SUPERVISOR_STATE_ROOT={state_root}",
        "-e",
        f"AGENT_SUPERVISOR_RUN_ID={run_id}",
        "-e",
        f"PYTHONPATH={source_root}",
    ]
    result = _tmux(
        ["new-session", "-d", "-s", name, *env, "--", "python3 -m agent_supervisor.worker"]
    )
    return result.returncode == 0


def interrupt(name: str) -> None:
    _tmux(["send-keys", "-t", f"={name}:0.0", "C-c"])


def kill(name: str) -> None:
    _tmux(["kill-session", "-t", f"={name}"])


def available() -> bool:
    try:
        return _tmux(["-V"]).returncode == 0
    except OSError:
        return False
