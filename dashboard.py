
from datetime import datetime
import platform

import pandas as pd
import streamlit as st

from aegisstate import AegisState, ProtectedExecutor
from aegisstate.benchmark import (
    GRAPH_SIZES,
    TRIALS,
    VALIDATIONS_PER_TRIAL,
    benchmark_validation,
    benchmark_invalidation,
)


st.set_page_config(
    page_title="AegisState | Control Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background: #0b1120;
        color: #e5edf8;
    }
    [data-testid="stSidebar"] {
        background: #101a2b;
        border-right: 1px solid #26364d;
    }
    [data-testid="stMetric"] {
        background: #121e30;
        border: 1px solid #26364d;
        padding: 16px;
        border-radius: 12px;
    }
    .hero {
        background: linear-gradient(120deg, #14243a, #102c38);
        border: 1px solid #285267;
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 20px;
    }
    .hero small, .section-label {
        color: #50d6c2;
        letter-spacing: 1.5px;
        font-weight: bold;
    }
    .hero h1 {
        color: #f3f7ff;
        margin-bottom: 8px;
    }
    .hero p, .muted {
        color: #a6b7ce;
    }
    .section-label {
        font-size: 12px;
    }
    .node {
        background: #121e30;
        border: 1px solid #2a3d56;
        border-radius: 10px;
        padding: 14px;
        margin: 5px 0;
    }
    .valid {
        border-left: 4px solid #32c995;
    }
    .stale {
        border-left: 4px solid #ff6577;
    }
    .denied {
        border-left: 4px solid #ffbd59;
    }
    .node-title {
        font-weight: bold;
        color: #edf4ff;
    }
    .node-detail {
        font-size: 12px;
        color: #9eb0c8;
        margin-top: 5px;
    }
    div.stButton > button {
        border-radius: 9px;
        min-height: 40px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def record_event(event_type, details):
    st.session_state.history.append({
        "time": datetime.now().astimezone().strftime(
            "%Y-%m-%d %H:%M:%S %z"
        ),
        "type": event_type,
        "details": details,
    })


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

    result = state.commit_decision(
        "risk_assessment",
        {"risk_score": risk_score},
    )
    if not result.get("committed", False):
        return False, risk_score, approved

    result = state.commit_decision(
        "approval",
        {"approved": approved, "risk_score": risk_score},
    )
    if not result.get("committed", False):
        return False, risk_score, approved

    if approved:
        result = state.commit_decision(
            "agent_action",
            {"action": "process_transaction"},
        )
        if not result.get("committed", False):
            return False, risk_score, approved
    else:
        state.set_version(
            "approval",
            state.versions["approval"] + 1,
        )

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
st.sidebar.title("🛡️ AEGISSTATE")
st.sidebar.caption("DECISION INTEGRITY PLATFORM")
st.sidebar.divider()
st.sidebar.subheader("Evidence controls")

st.sidebar.number_input(
    "Transaction amount",
    min_value=0,
    step=1000,
    value=st.session_state.amount,
    key="amount_input",
)
st.sidebar.selectbox(
    "Transaction status",
    ["pending", "completed", "cancelled"],
    index=["pending", "completed", "cancelled"].index(
        st.session_state.transaction_status
    ),
    key="status_input",
)

if st.sidebar.button(
    "Apply evidence change",
    type="primary",
    use_container_width=True,
):
    amount = st.session_state.amount_input
    status = st.session_state.status_input

    changed = (
        amount != st.session_state.amount
        or status != st.session_state.transaction_status
    )

    if changed:
        st.session_state.amount = amount
        st.session_state.transaction_status = status
        st.session_state.evidence_version += 1

        state.set_version(
            "transaction",
            st.session_state.evidence_version,
        )
        commit_transaction(state, amount, status)

        record_event(
            "EVIDENCE UPDATE",
            f"Transaction evidence changed to version "
            f"{st.session_state.evidence_version}.",
        )
    else:
        record_event(
            "NO CHANGE",
            "Submitted values match current evidence.",
        )

    st.rerun()

st.sidebar.divider()
st.sidebar.caption(
    "Local demonstration only. No live financial system or external "
    "agent is connected."
)

st.markdown(
    """
    <div class="hero">
        <small>AGENT DECISION INTEGRITY</small>
        <h1>Integrity Control Center</h1>
        <p>
            Monitor evidence, identify stale decisions, and protect
            actions that depend on valid approvals.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

risk_score = calculate_risk(
    st.session_state.amount,
    st.session_state.transaction_status,
)
policy_approves = (
    st.session_state.transaction_status == "pending"
    and risk_score < 50
)
approval_validation = state.validate("approval")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Evidence version", f"v{st.session_state.evidence_version}")
c2.metric("Risk score", f"{risk_score}/100")
c3.metric("Current policy", "APPROVE" if policy_approves else "DENY")
c4.metric(
    "Stored approval",
    "VALID" if approval_validation.get("valid", False) else "STALE",
)

st.caption(
    "Policy results use current inputs. Stored decisions are "
    "independently checked by AegisState."
)
st.divider()

st.markdown(
    '<div class="section-label">DEPENDENCY WORKSPACE</div>',
    unsafe_allow_html=True,
)
st.subheader("Decision dependency graph")

left, right = st.columns([3, 2])
workflow = [
    ("Transaction evidence", "transaction"),
    ("Risk assessment", "risk_assessment"),
    ("Approval decision", "approval"),
    ("Protected agent action", "agent_action"),
]

with left:
    for index, (label, item) in enumerate(workflow):
        result = state.validate(item)
        valid = result.get("valid", False)

        if not valid:
            css, status_text = "stale", "STALE / INVALID"
        elif item == "approval" and not policy_approves:
            css, status_text = "denied", "VALID · DENIED"
        else:
            css, status_text = "valid", "VALID"

        st.markdown(
            f"""
            <div class="node {css}">
                <div class="node-title">{label}</div>
                <div class="node-detail">{item}</div>
                <div class="node-detail">{status_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if index < len(workflow) - 1:
            st.markdown(
                '<div style="text-align:center;color:#50d6c2;'
                'font-size:22px;">↓</div>',
                unsafe_allow_html=True,
            )

with right:
    st.subheader("Evidence details")
    st.write("**Amount:**", f"{st.session_state.amount:,}")
    st.write("**Status:**", st.session_state.transaction_status)
    st.write("**Evidence version:**", st.session_state.evidence_version)
    st.write("**Risk score:**", risk_score)

    st.divider()
    st.subheader("Independent workflow")
    if state.validate("inventory_report").get("valid", False):
        st.success("Inventory report remains valid.")
    else:
        st.warning("Inventory report is stale or invalid.")
    st.caption(
        "Transaction updates should not invalidate the independent "
        "inventory workflow."
    )

st.divider()
st.markdown(
    '<div class="section-label">ACTION SECURITY</div>',
    unsafe_allow_html=True,
)
st.subheader("Protected execution")
st.write(
    "Attempt the demonstration action. The executor checks "
    "whether its required decision is valid."
)

if st.button("Attempt agent action", type="primary"):
    try:
        execution = executor.execute(
            "process_transaction",
            "agent_action",
            lambda: "Demonstration action completed",
        )
        if execution.get("executed", False):
            st.success("The protected executor permitted the action.")
            record_event("ACTION EXECUTED", "Demonstration action permitted.")
        else:
            st.error("The protected executor blocked the action.")
            record_event("ACTION BLOCKED", "Required decision was invalid.")
        st.json(execution)
    except Exception as error:
        st.error("The execution attempt raised an exception.")
        st.code(f"{type(error).__name__}: {error}")
        record_event("EXECUTION ERROR", f"{type(error).__name__}: {error}")

st.divider()
st.markdown(
    '<div class="section-label">DECISION MANAGEMENT</div>',
    unsafe_allow_html=True,
)
st.subheader("Recompute dependent decisions")
st.write(
    "Recalculate the risk assessment and approval using the "
    "current demonstration policy."
)

if st.button("Recompute decisions"):
    try:
        success, score, approved = recompute_decisions(
            state,
            st.session_state.amount,
            st.session_state.transaction_status,
        )
        if success:
            record_event(
                "DECISION RECOMPUTE",
                f"Recomputed at evidence version "
                f"{st.session_state.evidence_version}.",
            )
            if approved:
                st.success(f"Approval committed. Risk score: {score}/100.")
            else:
                st.warning(
                    f"Denial committed. Risk score: {score}/100. "
                    "The protected action should remain blocked."
                )
        else:
            st.error("Decision recomputation did not complete.")
            record_event("RECOMPUTE FAILURE", "Not all decisions committed.")
    except Exception as error:
        st.error("Decision recomputation raised an exception.")
        st.code(f"{type(error).__name__}: {error}")
        record_event("RECOMPUTE ERROR", f"{type(error).__name__}: {error}")
    st.rerun()

st.divider()
st.markdown(
    '<div class="section-label">AUDIT ACTIVITY</div>',
    unsafe_allow_html=True,
)
st.subheader("Security event feed")
history = st.session_state.history

st.caption(
    f"{len(history)} events recorded in this session. "
    "Showing the latest 10."
)
if history:
    for event in reversed(history[-10:]):
        with st.container(border=True):
            if isinstance(event, dict):
                st.caption(f"{event['time']} · {event['type']}")
                st.write(event["details"])
            else:
                st.write(event)
else:
    st.info("No events recorded yet.")

if st.button("Clear visible event history"):
    st.session_state.history = []
    st.rerun()

# NEW: Performance benchmark panel
st.divider()
st.markdown(
    '<div class="section-label">PERFORMANCE ANALYSIS</div>',
    unsafe_allow_html=True,
)
st.subheader("Dependency graph benchmark")
st.write(
    "Measure decision validation and root-change invalidation "
    "across dependency chains of increasing size."
)
st.caption(
    f"Graph sizes: {', '.join(map(str, GRAPH_SIZES))} nodes · "
    f"{TRIALS} trials · {VALIDATIONS_PER_TRIAL} validations per trial."
)

st.info(
    "This benchmark creates separate test graphs. It does not "
    "intentionally modify your live demonstration state."
)

if st.button("Run performance benchmark", type="primary"):
    results = []
    try:
        with st.spinner("Running benchmarks. Please wait..."):
            for size in GRAPH_SIZES:
                results.append({
                    "Graph size (nodes)": size,
                    "Validation median (ms)": round(
                        benchmark_validation(size), 3
                    ),
                    "Invalidation median (ms)": round(
                        benchmark_invalidation(size), 3
                    ),
                })

        st.session_state.benchmark_results = results
        st.session_state.benchmark_environment = {
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
        record_event(
            "BENCHMARK COMPLETE",
            f"Measured dependency chains: {GRAPH_SIZES}.",
        )
    except Exception as error:
        st.error("Benchmark failed.")
        st.code(f"{type(error).__name__}: {error}")

if "benchmark_results" in st.session_state:
    results = st.session_state.benchmark_results
    environment = st.session_state.benchmark_environment
    results_df = pd.DataFrame(results)

    st.success("Benchmark results are available.")
    st.dataframe(results_df, use_container_width=True, hide_index=True)

    st.markdown("### Latency by graph size")
    chart_df = results_df.set_index("Graph size (nodes)")[
        ["Validation median (ms)", "Invalidation median (ms)"]
    ]
    st.line_chart(chart_df)

    st.markdown("### Environment")
    st.write("**Python:**", environment["python"])
    st.write("**Platform:**", environment["platform"])
    st.caption(
        "Results represent this run only. Performance varies by hardware "
        "and system load; these measurements are not universal guarantees."
    )

st.divider()
st.caption(
    "AegisState · Local demonstration · "
    "Activity history is session-local and is not a persistent audit log."
)
