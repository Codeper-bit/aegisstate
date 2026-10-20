
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from aegisstate import AegisState, ProtectedExecutor


class WorkflowState(TypedDict):
    change_evidence: bool
    execution: dict
    status: str


def run_demo(change_evidence: bool):
    aegis = AegisState()
    executor = ProtectedExecutor(aegis)

    # AegisState's dependency graph
    aegis.add_item("transaction")
    aegis.add_item("risk_assessment")
    aegis.add_item("approval")

    aegis.add_dependency("risk_assessment", "transaction")
    aegis.add_dependency("approval", "risk_assessment")

    def make_decision(state: WorkflowState):
        risk = aegis.commit_decision(
            "risk_assessment",
            {"score": 20},
        )
        approval = aegis.commit_decision(
            "approval",
            {"approved": True},
        )

        assert risk["committed"], risk
        assert approval["committed"], approval

        return {"status": "Decision recorded"}

    def update_evidence(state: WorkflowState):
        if state["change_evidence"]:
            aegis.set_version("transaction", 2)
            return {"status": "Evidence changed"}

        return {"status": "Evidence unchanged"}

    def protected_action(state: WorkflowState):
        result = executor.execute(
            "process_approval",
            "approval",
            lambda: "Protected action completed",
        )

        return {
            "execution": result,
            "status": (
                "ACTION ALLOWED"
                if result["executed"]
                else "ACTION BLOCKED"
            ),
        }

    graph = StateGraph(WorkflowState)
    graph.add_node("make_decision", make_decision)
    graph.add_node("update_evidence", update_evidence)
    graph.add_node("protected_action", protected_action)

    graph.add_edge(START, "make_decision")
    graph.add_edge("make_decision", "update_evidence")
    graph.add_edge("update_evidence", "protected_action")
    graph.add_edge("protected_action", END)

    app = graph.compile()

    result = app.invoke({
        "change_evidence": change_evidence,
        "execution": {},
        "status": "Started",
    })

    return result


if __name__ == "__main__":
    print("\n=== LANGGRAPH + AEGISSTATE INTEGRATION ===")

    valid = run_demo(change_evidence=False)
    print("\nTEST 1: Current evidence")
    print(valid["status"])
    print(valid["execution"])
    assert valid["execution"]["executed"] is True

    stale = run_demo(change_evidence=True)
    print("\nTEST 2: Evidence changes before action")
    print(stale["status"])
    print(stale["execution"])
    assert stale["execution"]["executed"] is False

    print("\nPASS: Both integration scenarios behaved as expected.")
PY

python examples/langgraph_integration_demo.py
