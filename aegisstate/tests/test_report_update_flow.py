
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor
from aegisstate.evidence_updates import (
    TrustedEvidenceUpdater,
)
from aegisstate.report_bridge import (
    ReportBridge,
    StaleEvidenceError,
)


class TestReportUpdateFlow(unittest.TestCase):

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

        self.updater = TrustedEvidenceUpdater(self.state)
        self.bridge = ReportBridge(self.state)
        self.executor = ProtectedExecutor(self.state)

    def risk_report(self, version):
        return {
            "report_type": "risk_assessment",
            "decision_id": "risk_assessment",
            "evidence_id": "transaction",
            "evidence_version": version,
            "risk_score": 20,
        }

    def approval_report(self):
        return {
            "report_type": "approval",
            "decision_id": "approval",
            "evidence_id": "risk_assessment",
            "evidence_version": self.state.versions[
                "risk_assessment"
            ],
            "approved": True,
        }

    def test_old_report_rejected_after_trusted_update(self):
        self.updater.update_evidence("transaction")

        with self.assertRaises(StaleEvidenceError):
            self.bridge.process_report(
                self.risk_report(version=1)
            )

    def test_fresh_report_can_be_committed(self):
        self.updater.update_evidence("transaction")

        result = self.bridge.process_report(
            self.risk_report(version=2)
        )

        self.assertTrue(result["committed"])
        self.assertTrue(
            self.state.validate("risk_assessment")["valid"]
        )

    def test_full_flow_restores_protected_execution(self):
        # Update the trusted evidence source.
        self.updater.update_evidence("transaction")

        # The fresh risk report can now be accepted.
        self.bridge.process_report(
            self.risk_report(version=2)
        )

        # Commit an approval based on the fresh risk assessment.
        self.bridge.process_report(self.approval_report())

        # The executor permits the action only if approval is valid.
        result = self.executor.execute(
            "process_transaction",
            "approval",
            lambda: "Transaction processed",
        )

        self.assertTrue(result["executed"])


if __name__ == "__main__":
    unittest.main()
