
import unittest

from aegisstate.engine import AegisState
from aegisstate.report_bridge import (
    ReportBridge,
    StaleEvidenceError,
)


class TestReportBridge(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()

        self.state.add_item("transaction", version=1)
        self.state.add_item("risk_assessment")
        self.state.add_dependency(
            "risk_assessment",
            "transaction",
        )

        self.bridge = ReportBridge(self.state)

    def make_report(self, version=1):
        return {
            "report_type": "risk_assessment",
            "decision_id": "risk_assessment",
            "evidence_id": "transaction",
            "evidence_version": version,
            "risk_score": 20,
        }

    def test_current_report_is_accepted(self):
        result = self.bridge.process_report(
            self.make_report(version=1)
        )

        self.assertTrue(result["committed"])

    def test_stale_report_is_rejected(self):
        self.state.set_version("transaction", 2)

        with self.assertRaises(StaleEvidenceError):
            self.bridge.process_report(
                self.make_report(version=1)
            )

    def test_unknown_evidence_is_rejected(self):
        report = self.make_report()
        report["evidence_id"] = "missing_transaction"

        with self.assertRaises(ValueError):
            self.bridge.process_report(report)


if __name__ == "__main__":
    unittest.main()
