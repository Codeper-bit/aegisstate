class Agent:
    def __init__(self, state):
        self.state = state

    def execute(self, action_name):
        """Execute an action only if AegisState allows it."""

        decision = self.state.validate(action_name)

        if not decision["allowed"]:
            print(f"BLOCKED: {action_name}")
            print(f"Reason: {decision['reason']}")

            return False

        print(f"ALLOWED: {action_name}")
        print(f"Reason: {decision['reason']}")
        print("Action executed (simulation only).")

        return True
