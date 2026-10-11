
from engine import AegisState


state = AegisState()

print("\n=== AEGISSTATE DAY 4 ===")

# Build a branching dependency graph.
state.add_dependency(
    "risk_assessment",
    "transaction"
)

state.add_dependency(
    "approval",
    "risk_assessment"
)

state.add_dependency(
    "approval",
    "account_status"
)

state.add_dependency(
    "approval",
    "account_balance"
)

state.add_dependency(
    "agent_action",
    "approval"
)

# Create an unrelated decision.
state.add_dependency(
    "inventory_report",
    "inventory_data"
)

# Record decisions in dependency order.
items = [
    "risk_assessment",
    "approval",
    "agent_action",
    "inventory_report"
]

print("\n1. Recording decisions")

for item in items:
    print(item, state.record_decision(item))

# Check initial validity.
print("\n2. Initial validation")

print(
    "Agent action:",
    state.validate("agent_action")
)

print(
    "Inventory report:",
    state.validate("inventory_report")
)

# Change one dependency of the approval.
print("\n3. Account balance changes")

affected = state.set_version(
    "account_balance",
    2
)

print("Affected decisions:", affected)

# Check selective invalidation.
print("\n4. Validate after the change")

print(
    "Agent action:",
    state.validate("agent_action")
)

print(
    "Inventory report:",
    state.validate("inventory_report")
)

# Show the engine state.
print("\n5. Final snapshot")

print(state.snapshot())
