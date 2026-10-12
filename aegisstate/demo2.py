
from engine import AegisState
from executor import ProtectedExecutor


def read_transaction(label):
    """Collect transaction evidence at runtime."""
    print(f"\n--- {label} ---")

    while True:
        try:
            amount = float(input("Transaction amount: "))

            if amount < 0:
                print("Amount cannot be negative.")
                continue

            break
        except ValueError:
            print("Enter a valid number.")

    while True:
        status = input(
            "Transaction status (pending/completed/cancelled): "
        ).strip().lower()

        if status in {"pending", "completed", "cancelled"}:
            break

        print("Enter pending, completed, or cancelled.")

    return {
        "amount": amount,
        "status": status,
    }


def calculate_risk(transaction):
    """Calculate a demonstration risk score from the evidence."""
    amount = transaction["amount"]
    status = transaction["status"]

    if status != "pending":
        return 100
    if amount > 100_000:
        return 80
    if amount > 50_000:
        return 60

    return 20


def process_decisions(state, transaction):
    """Recalculate decisions using the current transaction evidence."""
    risk_score = calculate_risk(transaction)

    approval = (
        risk_score < 50
        and transaction["status"] == "pending"
    )

    state.commit_decision(
        "risk_assessment",
        {
            "risk_score": risk_score,
            "based_on": transaction.copy(),
        },
    )

    state.commit_decision(
        "approval",
        {
            "approved": approval,
            "risk_score": risk_score,
        },
    )

    print(f"Calculated risk score: {risk_score}")
    print(f"Approval decision: {approval}")

    return approval


def main():
    state = AegisState()
    executor = ProtectedExecutor(state)

    state.add_item("transaction", version=1)
    state.add_item("risk_assessment")
    state.add_item("approval")
    state.add_item("agent_action")

    state.add_dependency("risk_assessment", "transaction")
    state.add_dependency("approval", "risk_assessment")
    state.add_dependency("agent_action", "approval")

    # First transaction input.
    first_transaction = read_transaction("FIRST TRANSACTION")

    print("\n--- FIRST DECISION ---")
    first_approved = process_decisions(state, first_transaction)

    if first_approved:
        state.commit_decision(
            "agent_action",
            {"action": "process_transaction"},
        )

    first_result = executor.execute(
        "process_transaction",
        "agent_action",
        lambda: "Transaction action executed",
    )
    print("Execution result:", first_result)

    # Read the evidence again to detect changes.
    second_transaction = read_transaction("UPDATED TRANSACTION")

    if second_transaction == first_transaction:
        print("\nEvidence has not changed.")
        print("No new version is required.")
        return

    print("\nEvidence changed! Updating transaction version...")
    state.set_version("transaction", 2)

    print("\n--- STALE DECISION CHECK ---")
    print(state.validate("agent_action"))

    print("\n--- RECOMPUTING DECISIONS ---")
    second_approved = process_decisions(state, second_transaction)

    if second_approved:
        # Commit a fresh action decision based on fresh approval.
        state.commit_decision(
            "agent_action",
            {"action": "process_updated_transaction"},
        )
    else:
        print("No new action decision will be committed.")

    print("\n--- FINAL EXECUTION CHECK ---")
    final_result = executor.execute(
        "process_transaction",
        "agent_action",
        lambda: "Transaction action executed",
    )
    print("Execution result:", final_result)


if __name__ == "__main__":
    main()
