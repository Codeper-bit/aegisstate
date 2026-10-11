class ProtectedExecutor:
    def __init__(self, state):
        self.state = state
        self.execution_log = []

    def execute(self, action_name, required_decision, action):
        """
        Execute an action only if its required decision is valid.
        """

        validation = self.state.validate(required_decision)

        if not validation["valid"]:
            result = {
                "executed": False,
                "action": action_name,
                "reason": validation["reason"],
            }

            self.execution_log.append(result)
            return result

        action_result = action()

        result = {
            "executed": True,
            "action": action_name,
            "result": action_result,
        }

        self.execution_log.append(result)
        return result

    def get_execution_log(self):
        return list(self.execution_log)
