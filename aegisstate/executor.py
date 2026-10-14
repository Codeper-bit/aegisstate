from collections import deque

DEFAULT_MAX_LOG_ENTRIES = 10_000
MAX_LOGGED_ERROR_CHARS = 200


class ProtectedExecutor:
    """Runs an action only while the decision it relies on is valid.

    The execution log is bounded (oldest entries are dropped first) so a
    long-running process cannot grow memory without limit. Pass
    ``max_log_entries=None`` for an unbounded log.

    The log records the outcome of each action but not the object it
    returned (``log_results=False``): keeping up to 10,000 arbitrarily large
    results alive is a memory leak, and results can contain sensitive data.
    """

    def __init__(
        self,
        state,
        max_log_entries=DEFAULT_MAX_LOG_ENTRIES,
        log_results=False,
    ):
        if max_log_entries is not None and (
            not isinstance(max_log_entries, int)
            or isinstance(max_log_entries, bool)
            or max_log_entries < 1
        ):
            raise ValueError(
                "max_log_entries must be a positive integer or None"
            )

        self.state = state
        self.log_results = log_results
        self.execution_log = deque(maxlen=max_log_entries)

    def execute(self, action_name, required_decision, action):
        if not callable(action):
            raise TypeError("action must be callable")

        validation = self.state.validate(required_decision)

        if not validation["valid"]:
            result = {
                "executed": False,
                "action": action_name,
                "reason": validation["reason"],
            }

            self.execution_log.append(result)
            return dict(result)

        try:
            action_result = action()
        except Exception as exc:
            # Keep an audit trail of failed actions, then re-raise.
            # The message is truncated: exception text can be huge or
            # contain secrets.
            message = str(exc)[:MAX_LOGGED_ERROR_CHARS]
            self.execution_log.append({
                "executed": False,
                "action": action_name,
                "reason": f"Action raised {type(exc).__name__}: {message}",
            })
            raise

        result = {
            "executed": True,
            "action": action_name,
            "result": action_result,
        }

        logged = dict(result)
        if not self.log_results:
            del logged["result"]
        self.execution_log.append(logged)
        return dict(result)

    def get_execution_log(self):
        return list(self.execution_log)
