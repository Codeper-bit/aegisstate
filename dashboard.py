import streamlit as st

from aegisstate import AegisState, ProtectedExecutor


st.set_page_config(
    page_title="AegisState Integrity Monitor",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ AegisState Integrity Monitor")
st.caption("Dependency-aware temporal integrity for AI-agent decisions")

st.info(
    "Change transaction evidence, observe stale decisions, attempt the "
    "protected action, and then test recovery."
)


def create_system():
    state = AegisState()
    executor = ProtectedExecutor(state)

    items = [
        "transaction",
        "risk_assessment",
        "approval",
        "agent_action",
        "inventory_data",
        "inventory_report",
    ]

    for item in items:
        state.add_item(item)

    state.add_dependency("risk_assessment", "transaction")
    state.add_dependency("approval", "risk_assessment")
    state.add_dependency("agent_action", "approval")
    state.add_dependency("inventory_report", "inventory_data")

    return state, executor


def calculate_risk(amount, status):
    if status != "pending":
        return 100
    if amount > 100_000:
        return 80
    if amount > 50_000:
        return 60
    return 20


def commit_transaction(state, amount, status):
    return state.commit_decision(
        "transaction",
        {"amount": amount, "status": status},
    )


def recompute_decisions(state, amount, status):
    risk_score = calculate_risk(amount, status)
    approved = status == "pending" and risk_score < 50

    risk_result = state.commit_decision(
        "risk_assessment",
        {
            "risk_score": risk_score,
            "based_on": {"amount": amount, "status": status},
        },
    )
    if not risk_result.get("committed", False):
        return False, risk_score, approved

    approval_result = state.commit_decision(
        "approval",
        {"approved": approved, "risk_score": risk_score},
    )
    if not approval_result.get("committed", False):
        return False, risk_score, approved

    # Do not create an actionable decision when the policy denies approval.
    if approved:
        action_result = state.commit_decision(
            "agent_action",
            {"action": "process_transaction"},
        )
        if not action_result.get("committed", False):
            return False, risk_score, approved

    return True, risk_score, approved


if "system" not in st.session_state:
    state, executor = create_system()
    st.session_state.system = (state, executor)
    st.session_state.evidence_version = 1
    st.session_state.amount = 1000
    st.session_state.transaction_status = "pending"
    st.session_state.history = []
    st.session_state.initialized = False

state, executor = st.session_state.system

if not st.session_state.initialized:
    commit_transaction(
        state,
        st.session_state.amount,
        st.session_state.transaction_status,
    )
    state.commit_decision("inventory_data", {"stock": 50})
    state.commit_decision(
        "inventory_report",
        {"stock": 50, "report": "Inventory checked"},
    )
    recompute_decisions(
        state,
        st.session_state.amount,
        st.session_state.transaction_status,
    )
    st.session_state.initialized = True


st.sidebar.header("Transaction Evidence")
amount = st.sidebar.number_input(
    "Transaction amount",
    min_value=0,
    value=st.session_state.amount,
    step=1000,
    key="amount_input",
)
status = st.sidebar.selectbox(
    "Transaction status",
    ["pending", "completed", "cancelled"],
    index=["pending", "completed", "cancelled"].index(
        st.session_state.transaction_status
    ),
    key="status_input",
)

if st.sidebar.button("Apply evidence change", type="primary"):
    new_amount = st.session_state.amount_input
    new_status = st.session_state.status_input

    # Only change the evidence version when the evidence actually changes.
    if (
        new_amount != st.session_state.amount
        or new_status != st.session_state.transaction_status
    ):
        st.session_state.amount = new_amount
        st.session_state.transaction_status = new_status
        st.session_state.evidence_version += 1

        state.set_version("transaction", st.session_state.evidence_version)
        commit_transaction(state, new_amount, new_status)

        st.session_state.history.append(
            f"Evidence changed to version {st.session_state.evidence_version}"
        )
    else:
        st.session_state.history.append("No evidence change detected.")

    st.rerun()


risk_score = calculate_risk(
    st.session_state.amount,
    st.session_state.transaction_status,
)
current_policy_approves = (
    st.session_state.transaction_status == "pending" and risk_score < 50
)

st.subheader("System Overview")
col1, col2, col3 = st.columns(3)
col1.metric("Evidence Version", st.session_state.evidence_version)
col2.metric("Current Risk Score", risk_score)
col3.metric(
    "Current Policy Result",
    "Approved" if current_policy_approves else "Denied",
)
st.caption(
    "The current policy result is calculated from the displayed inputs. "
    "It does not mean the stored approval has been refreshed."
)

st.divider()
st.subheader("Decision Dependency Graph")
graph_col, details_col = st.columns([3, 2])

with graph_col:
    st.markdown("### Transaction workflow")
    nodes = [
        ("Transaction", "transaction"),
        ("Risk Assessment", "risk_assessment"),
        ("Approval", "approval"),
        ("Agent Action", "agent_action"),
    ]

    for index, (label, item) in enumerate(nodes):
        result = state.validate(item)
        if not result.get("valid", False):
            st.error(f"● {label} — STALE / INVALID")
        elif item == "approval" and not current_policy_approves:
            st.warning(f"● {label} — VALID DECISION, DENIED")
        else:
            st.success(f"● {label} — VALID")

        if index < len(nodes) - 1:
            st.markdown("↓")

    st.markdown("### Independent workflow")
    inventory_result = state.validate("inventory_report")
    if inventory_result.get("valid", False):
        st.success("● Inventory Report — VALID")
    else:
        st.error("● Inventory Report — INVALID")

with details_col:
    st.markdown("### Evidence Details")
    st.write("**Amount:**", st.session_state.amount)
    st.write("**Status:**", st.session_state.transaction_status)
    st.write("**Version:**", st.session_state.evidence_version)
    st.write("**Current risk score:**", risk_score)

st.divider()
st.subheader("Protected Execution")
if st.button("Attempt agent action"):
    execution = executor.execute(
        "process_transaction",
        "agent_action",
        lambda: "Demonstration action completed",
    )
    if execution.get("executed", False):
        st.success("The protected executor permitted the action.")
    else:
        st.error("The protected executor blocked the action.")
    st.json(execution)

st.divider()
st.subheader("Recompute Decisions")
st.write(
    "After evidence changes, explicitly recompute the risk assessment "
    "and approval. A new agent-action decision is created only if the "
    "current demonstration policy approves the transaction."
)

if st.button("Recompute decisions"):
    success, new_risk, new_approval = recompute_decisions(
        state,
        st.session_state.amount,
        st.session_state.transaction_status,
    )

    if success:
        st.session_state.history.append(
            f"Decisions recomputed at evidence version "
            f"{st.session_state.evidence_version}"
        )
        if new_approval:
            st.success(
                f"Fresh decisions committed. Risk score: {new_risk}. "
                "Try the protected action again."
            )
        else:
            st.warning(
                f"Fresh risk assessment and denial committed. "
                f"Risk score: {new_risk}. The action remains unavailable."
            )
    else:
        st.error(
            "Decision recomputation failed. Check the engine validation "
            "result and dependency configuration."
        )
    st.rerun()

st.divider()
st.subheader("Evidence Change History")
if st.session_state.history:
    for event in reversed(st.session_state.history):
        st.write(f"• {event}")
else:
    st.write("No evidence changes recorded yet.")
