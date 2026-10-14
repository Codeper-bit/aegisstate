
import tempfile
import unittest
from pathlib import Path

from aegisstate.engine import AegisState
from aegisstate.report_ingestion import ReportValidationError
from aegisstate.report_security import ReplayProtectedReportBridge
from aegisstate.replay_store import SQLiteReplayStore


class TestPersistentReportRecovery(unittest.TestCase):

    def test_invalid_report_can_be_corrected_and_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"

            state = AegisState()
            state.add_item("transaction")
            state.add_item("risk_assessment")
            state.add_dependency("risk_assessment", "transaction")

            store = SQLiteReplayStore(database)
            bridge = ReplayProtectedReportBridge(
                state,
                replay_store=store,
            )

            report = {
                "report_id": "retry-report-001",
                "decision_id": "risk_assessment",
                "evidence_id": "transaction",
                "evidence_version": 1,
                "risk_score": 0.2,
            }

            # The first submission is invalid because report_type is missing.
            with self.assertRaises(ReportValidationError):
                bridge.process_report(report)

            # Correct the report and retry using the same report ID.
            report["report_type"] = "risk_assessment"

            result = bridge.process_report(report)

            self.assertTrue(result["committed"])


if __name__ == "__main__":
    unittest.main()
