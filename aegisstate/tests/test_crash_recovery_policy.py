
import tempfile
import unittest
from pathlib import Path

from aegisstate.replay_store import SQLiteReplayStore


class TestCrashRecoveryPolicy(unittest.TestCase):

    def test_processing_report_stays_blocked_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"

            first_store = SQLiteReplayStore(database)
            self.assertTrue(first_store.reserve("report-crash-1"))

            # Simulate a restart before processing finishes.
            second_store = SQLiteReplayStore(database)

            self.assertEqual(
                second_store.get_status("report-crash-1"),
                "processing",
            )
            self.assertFalse(
                second_store.reserve("report-crash-1")
            )

    def test_recovery_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"
            store = SQLiteReplayStore(database)

            store.reserve("report-crash-2")

            with self.assertRaises(ValueError):
                store.recover_abandoned("report-crash-2")

            self.assertEqual(
                store.get_status("report-crash-2"),
                "processing",
            )

    def test_confirmed_recovery_allows_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"
            store = SQLiteReplayStore(database)

            store.reserve("report-crash-3")

            store.recover_abandoned(
                "report-crash-3",
                confirmed_not_committed=True,
            )

            self.assertIsNone(
                store.get_status("report-crash-3")
            )
            self.assertTrue(store.reserve("report-crash-3"))


if __name__ == "__main__":
    unittest.main()
