from engine import AegisState
from agent import Agent


def build_demo():
    state = AegisState()

    # Main dependency chain.
    state.add_dependency(
        "risk_assessment",
        "transaction"
    )

    state.add_dependency(
        "approval",
        "risk_assessment"
    )

    state.add_dependency(
        "agent_action",
        "approval"
    )

    # An independent chain.
    state.add_dependency(
        "other_action",
        "other_transaction"
    )

    return state


def main():
    state = build_demo()
    agent = Agent(state)

    print("=" * 60)
    print("AEGISSTATE — DAY 1 DEMONSTRATION")
    print("=" * 60)

    # TEST 1: Initial state.
    print("\n[TEST 1] INITIAL STATE")

    agent.execute("agent_action")
    agent.execute("other_action")

    # TEST 2: Change the underlying transaction.
    print("\n[TEST 2] TRANSACTION CHANGES")

    affected = state.set_version(
        "transaction",
        2
    )

    print(
        "Automatically invalidated:",
        sorted(affected)
    )

    # TEST 3: Try the affected action.
    print("\n[TEST 3] AFFECTED ACTION")

    agent.execute("agent_action")

    # TEST 4: Try the independent action.
    print("\n[TEST 4] UNRELATED ACTION")

    agent.execute("other_action")

    # TEST 5: Try refreshing too early.
    print("\n[TEST 5] EARLY REFRESH")

    result = state.refresh("agent_action")

    print(result)

    # TEST 6: Refresh in dependency order.
    print("\n[TEST 6] REFRESH DEPENDENCIES")

    print(
        state.refresh(
            "risk_assessment",
            new_version=2
        )
    )

    print(
        state.refresh(
            "approval",
            new_version=2
        )
    )

    print(
        state.refresh(
            "agent_action",
            new_version=2
        )
    )

    # TEST 7: Retry the action.
    print("\n[TEST 7] FINAL VALIDATION")

    agent.execute("agent_action")

    # TEST 8: Show engine state.
    print("\n[TEST 8] FINAL ENGINE SNAPSHOT")

    print(state.snapshot())


if __name__ == "__main__":
    main()
