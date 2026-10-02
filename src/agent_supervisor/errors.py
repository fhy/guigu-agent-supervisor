class SupervisorError(Exception):
    def __init__(self, exit_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message


def invalid(message: str) -> SupervisorError:
    return SupervisorError(2, "invalid_request", message)


def unsafe(message: str) -> SupervisorError:
    return SupervisorError(3, "unsafe_path_or_conflict", message)


def not_found() -> SupervisorError:
    return SupervisorError(4, "run_not_found", "run not found")


def invalid_state(message: str) -> SupervisorError:
    return SupervisorError(5, "invalid_state", message)


def process_failure(message: str) -> SupervisorError:
    return SupervisorError(6, "process_failure", message)


def result_error(message: str) -> SupervisorError:
    return SupervisorError(7, "result_unavailable", message)
