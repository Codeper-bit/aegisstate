
import unittest

from engine import AegisState
from aegisstate.report_security import (
    ReplayProtectedReportBridge,
    ReportReplayError,
)


class TestReportReplayProtection(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()
        self.state.add_item("transaction", version=1)
        self.state.add_item("risk_assessment")
        self.state.add_dependency(
            "risk_assessment", "transaction"
        )

        self.bridge = ReplayProtectedReportBridge(self.state)

    def make_report(self, report_id="report-001", version=1):
        return {
            "report_id": report_id,
            "report_type": "risk_assessment",
            "decision_id": "risk_assessment",
            "evidence_id": "transaction",
            "evidence_version": version,
            "risk_score": 20,
        }

    def test_first_submission_is_accepted(self):
        result = self.bridge.process_report(self.make_report())
        self.assertTrue(result["committed"])

    def test_duplicate_report_is_rejected(self):
        report = self.make_report()
        self.bridge.process_report(report)

        with self.assertRaises(ReportReplayError):
            self.bridge.process_report(report)

    def test_report_id_is_required(self):
        report = self.make_report()
        del report["report_id"]

        with self.assertRaises(ReportReplayError):
            self.bridge.process_report(report)

    def test_failed_report_id_can_be_retried(self):
        # Version 2 is stale while the registered version is 1.
        report = self.make_report(
            report_id="retry-001", version=2
        )

        with self.assertRaises(ValueError):
            self.bridge.process_report(report)

        # Correct the report to use the current version.
        report["evidence_version"] = 1

        result = self.bridge.process_report(report)
        self.assertTrue(result["committed"])

    def test_old_report_is_rejected_after_evidence_update(self):
        report = self.make_report()
        self.bridge.process_report(report)

        self.state.set_version("transaction", 2)

        with self.assertRaises(ReportReplayError):
            self.bridge.process_report(report)


if __name__ == "__main__":
    unittest.main()
