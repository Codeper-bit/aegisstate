
import os
import tempfile
import unittest
from pathlib import Path

from aegisstate.replay_store import (
    InMemoryReplayStore,
    SQLiteReplayStore,
)


class TestReplayStores(unittest.TestCase):

    def test_memory_store_rejects_duplicate_id(self):
        store = InMemoryReplayStore()

        self.assertTrue(store.reserve("report-1"))
        self.assertFalse(store.reserve("report-1"))

    def test_sqlite_store_remembers_id_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"

            first_store = SQLiteReplayStore(database)
            self.assertTrue(first_store.reserve("report-1"))
            first_store.mark_processed("report-1")

            second_store = SQLiteReplayStore(database)
            self.assertFalse(second_store.reserve("report-1"))

    def test_failed_reservation_can_be_released(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"

            store = SQLiteReplayStore(database)
            self.assertTrue(store.reserve("report-2"))

            store.release("report-2")

            self.assertTrue(store.reserve("report-2"))

    def test_sqlite_store_leaves_no_open_file_handles(self):
        # Regression: connections used to stay open, which on Windows made
        # TemporaryDirectory cleanup fail with WinError 32.
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"
            store = SQLiteReplayStore(database)
            store.reserve("a")
            store.mark_processed("a")
            store.reserve("b")
            store.release("b")

            if os.path.isdir("/proc/self/fd"):
                open_files = [
                    os.readlink(f"/proc/self/fd/{fd}")
                    for fd in os.listdir("/proc/self/fd")
                    if os.path.exists(f"/proc/self/fd/{fd}")
                ]
                self.assertFalse(
                    [f for f in open_files if f.startswith(directory)]
                )

            os.remove(database)  # raises PermissionError if still locked

    def test_memory_database_works_across_operations(self):
        with SQLiteReplayStore(":memory:") as store:
            self.assertTrue(store.reserve("x"))
            self.assertFalse(store.reserve("x"))
            store.mark_processed("x")
            store.release("x")  # processed IDs are not releasable
            self.assertFalse(store.reserve("x"))

    def test_mark_processed_requires_reservation(self):
        with SQLiteReplayStore(":memory:") as store:
            with self.assertRaises(ValueError):
                store.mark_processed("never-reserved")

    def test_invalid_report_ids_are_rejected(self):
        for store in (InMemoryReplayStore(), SQLiteReplayStore(":memory:")):
            for bad in ("", "   ", None, 5):
                with self.assertRaises(ValueError):
                    store.reserve(bad)


if __name__ == "__main__":
    unittest.main()
