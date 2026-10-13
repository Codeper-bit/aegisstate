
import unittest

from engine import AegisState
from executor import ProtectedExecutor
from aegisstate.report_bridge import ReportBridge, StaleEvidenceError


class TestEndToEndProtection(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()

        self.state.add_item("transaction", version=1)
        self.state.add_item("risk_assessment")
        self.state.add_item("approval")
        self.state.add_item("agent_action")

        self.state.add_dependency(
            "risk_assessment", "transaction"
        )
        self.state.add_dependency(
            "approval", "risk_assessment"
        )
        self.state.add_dependency(
            "agent_action", "approval"
        )

        self.bridge = ReportBridge(self.state)
        self.executor = ProtectedExecutor(self.state)

    def report(self, decision_id, evidence_id, **fields):
        return {
            "report_type": fields.pop(
                "report_type", "risk_assessment"
            ),
            "decision_id": decision_id,
            "evidence_id": evidence_id,
            "evidence_version": fields.pop(
                "evidence_version", 1
            ),
            **fields,
        }

    def test_stale_report_is_rejected(self):
        self.state.set_version("transaction", 2)

        with self.assertRaises(StaleEvidenceError):
            self.bridge.process_report(
                self.report(
                    "risk_assessment",
                    "transaction",
                    risk_score=20,
                )
            )

    def test_stale_approval_blocks_action(self):
        self.state.commit_decision(
            "risk_assessment", {"risk_score": 20}
        )
        self.state.commit_decision(
            "approval", {"approved": True}
        )

        self.state.set_version("transaction", 2)

        result = self.executor.execute(
            "process_transaction",
            "approval",
            lambda: "ACTION RAN",
        )

        self.assertFalse(result["executed"])

    def test_unrelated_decision_remains_valid(self):
        self.state.add_item("inventory_data")
        self.state.add_item("inventory_report")
        self.state.add_dependency(
            "inventory_report", "inventory_data"
        )

        self.state.commit_decision(
            "inventory_report", {"count": 10}
        )

        self.state.set_version("transaction", 2)

        self.assertTrue(
            self.state.validate("inventory_report")["valid"]
        )


if __name__ == "__main__":
    unittest.main()
