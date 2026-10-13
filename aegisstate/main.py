
from aegisstate.engine import AegisState


state = AegisState()


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

print("\n1. Initial decision commits")

print(
    state.commit_decision(
        "risk_assessment",
        {"risk_score": 20}
    )
)

print(
    state.commit_decision(
        "approval",
        {"approved": True}
    )
)

print(
    state.commit_decision(
        "agent_action",
        {"action": "execute_transaction"}
    )
)

print("\n2. Validate original action")

print(state.validate("agent_action"))

print("\n3. Transaction changes")

print(
    "Invalidated:",
    state.set_version("transaction", 2)
)

print(
    "Agent action:",
    state.validate("agent_action")
)

print("\n4. Try premature recovery")

print(
    state.commit_decision(
        "approval",
        {"approved": True}
    )
)

print("\n5. Recalculate risk assessment")

print(
    state.commit_decision(
        "risk_assessment",
        {"risk_score": 35}
    )
)

print("\n6. Recalculate approval")

print(
    state.commit_decision(
        "approval",
        {"approved": True}
    )
)

print("\n7. Recalculate agent action")

print(
    state.commit_decision(
        "agent_action",
        {"action": "execute_transaction"}
    )
)

print("\n8. Final validation")

print(state.validate("agent_action"))

print("\n9. Final snapshot")

print(state.snapshot())
