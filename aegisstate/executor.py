from collections import deque

DEFAULT_MAX_LOG_ENTRIES = 10_000


class ProtectedExecutor:
    """Runs an action only while the decision it relies on is valid.

    The execution log is bounded (oldest entries are dropped first) so a
    long-running process cannot grow memory without limit. Pass
    ``max_log_entries=None`` for an unbounded log.
    """

    def __init__(
        self, state, max_log_entries=DEFAULT_MAX_LOG_ENTRIES
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
        self.execution_log = deque(maxlen=max_log_entries)

    def execute(self, action_name, required_decision, action):

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
            self.execution_log.append({
                "executed": False,
                "action": action_name,
                "reason": f"Action raised {type(exc).__name__}: {exc}",
            })
            raise

        result = {
            "executed": True,
            "action": action_name,
            "result": action_result,
        }

        self.execution_log.append(result)
        return dict(result)

    def get_execution_log(self):
        return list(self.execution_log)
