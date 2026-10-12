from aegisstate import AegisState, ProtectedExecutor


def main():
    state = AegisState()
    executor = ProtectedExecutor(state)

# Register the evidence and the decisions that depend on it.
    state.add_item("transaction")
    state.add_item("risk_assessment")
    state.add_item("approval")
    state.add_item("agent_action")

    state.add_dependency("risk_assessment", "transaction")
    state.add_dependency("approval", "risk_assessment")
    state.add_dependency("agent_action", "approval")

# Record the initial transaction evidence.
    state.commit_decision(
        "transaction",
        {"amount": 1000, "status": "pending"},
    )

# Record the risk assessment and approval.
    state.commit_decision(
        "risk_assessment",
        {"risk_score": 20},
    )

    state.commit_decision(
        "approval",
        {"approved": True},
    )

    state.commit_decision(
        "agent_action",
        {"action": "process_transaction"},
    )

# Change the underlying evidence.
    print("Changing transaction evidence...")
    state.set_version("transaction", 2)

# Attempt the action using the old decision.
    result = executor.execute(
        "process_transaction",
        "agent_action",
        lambda: "Transaction processed",
    )

    print("Execution result:", result)


if __name__ == "__main__":
    main()
