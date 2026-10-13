
import tempfile
import unittest
from pathlib import Path

from engine import AegisState
from aegisstate.report_security import (
    ReplayProtectedReportBridge,
    ReportReplayError,
)
from aegisstate.replay_store import SQLiteReplayStore


class TestPersistentReportSecurity(unittest.TestCase):

    def test_duplicate_report_stays_blocked_after_store_reopens(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"

            state = AegisState()
            state.add_item("transaction")
            state.add_item("risk_assessment")
            state.add_dependency(
                "risk_assessment",
                "transaction",
            )

            report = {
                "report_id": "persistent-report-001",
                "report_type": "risk_assessment",
                "decision_id": "risk_assessment",
                "evidence_id": "transaction",
                "evidence_version": 1,
                "risk_score": 0.2,
            }

            first_bridge = ReplayProtectedReportBridge(
                state,
                replay_store=SQLiteReplayStore(database),
            )

            result = first_bridge.process_report(report)
            self.assertTrue(result["committed"])

            # Reopen the SQLite store and create a new bridge.
            second_bridge = ReplayProtectedReportBridge(
                state,
                replay_store=SQLiteReplayStore(database),
            )

            with self.assertRaises(ReportReplayError):
                second_bridge.process_report(report)


if __name__ == "__main__":
    unittest.main()
