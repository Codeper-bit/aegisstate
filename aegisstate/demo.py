
from engine import AegisState
from executor import ProtectedExecutor


def main():
    state = AegisState()
    executor = ProtectedExecutor(state)

    state.add_item("transaction")
    state.add_item("risk_assessment")
    state.add_item("approval")
    state.add_item("agent_action")
    state.add_item("inventory_report")
    state.add_item("inventory_data")

    state.add_dependency("risk_assessment", "transaction")
    state.add_dependency("approval", "risk_assessment")
    state.add_dependency("agent_action", "approval")

    state.add_dependency("inventory_report", "inventory_data")

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
        {"action": "execute_transaction"},
    )
    state.commit_decision(
        "inventory_report",
        {"items_available": 120},
    )

    print("\n1. Initial decisions recorded.")

    result = executor.execute(
        "execute_transaction",
        "agent_action",
        lambda: "Transaction executed",
    )
    print("Initial execution:", result)

    state.set_version("transaction", 2)

    print("\n2. Transaction evidence changed.")

    print(
        "Risk assessment:",
        state.validate("risk_assessment"),
    )
    print("Approval:", state.validate("approval"))
    print("Agent action:", state.validate("agent_action"))
    print(
        "Inventory report:",
        state.validate("inventory_report"),
    )

    blocked = executor.execute(
        "execute_transaction",
        "agent_action",
        lambda: "Transaction executed",
    )
    print("\n3. Attempt using stale approval:", blocked)

    state.commit_decision(
        "risk_assessment",
        {"risk_score": 35},
    )
    state.commit_decision(
        "approval",
        {"approved": True},
    )
    state.commit_decision(
        "agent_action",
        {"action": "execute_transaction"},
    )

    print("\n4. Decisions recalculated.")

    recovered = executor.execute(
        "execute_transaction",
        "agent_action",
        lambda: "Transaction executed after revalidation",
    )
    print("Execution after recovery:", recovered)


if __name__ == "__main__":
    main()
