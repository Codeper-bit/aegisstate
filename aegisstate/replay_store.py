import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


def _check_report_id(report_id):
    if not isinstance(report_id, str) or not report_id.strip():
        raise ValueError("report_id must be a non-empty string.")


class InMemoryReplayStore:
    """Replay storage that lasts only while the process is running.

    Every reserved ID is remembered for the life of the process. Evicting
    old IDs would re-open the door to replay attacks, so use
    SQLiteReplayStore (and prune it deliberately) for long-running services.
    """

    def __init__(self):
        self._report_ids = set()
        self._lock = threading.Lock()

    def reserve(self, report_id):
        _check_report_id(report_id)

        with self._lock:
            if report_id in self._report_ids:
                return False

            self._report_ids.add(report_id)
            return True

    def mark_processed(self, report_id):
        # The ID is already reserved.
        with self._lock:
            if report_id not in self._report_ids:
                raise ValueError("Report ID was not reserved.")

    def release(self, report_id):
        with self._lock:
            self._report_ids.discard(report_id)

    def close(self):
        """Nothing to release; present for interface parity."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class SQLiteReplayStore:
    """Persistent replay storage backed by SQLite.

    Connections are always closed after each operation. (A plain
    ``with sqlite3.connect(...)`` only commits or rolls back; it does NOT
    close the connection, which leaks handles and, on Windows, keeps the
    database file locked: ``WinError 32``.)

    ``":memory:"`` databases are private to a single connection, so for that
    path one connection is kept open until close() is called.
    """

    def __init__(self, database_path):
        self.database_path = str(database_path)
        self._lock = threading.RLock()
        self._memory_connection = None

        if self.database_path == ":memory:":
            self._memory_connection = sqlite3.connect(
                ":memory:", check_same_thread=False
            )
        else:
            Path(self.database_path).parent.mkdir(
                parents=True, exist_ok=True
            )

        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS replay_reports (
                    report_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                        CHECK (status IN ('processing', 'processed'))
                )
            """)

    @contextmanager
    def _connection(self):
        """Yield a connection; commit on success, roll back on error,
        and ALWAYS close file-backed connections."""
        with self._lock:
            if self._memory_connection is not None:
                connection = self._memory_connection
                owns_connection = False
            else:
                connection = sqlite3.connect(
                    self.database_path, timeout=10
                )
                owns_connection = True

            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                if owns_connection:
                    connection.close()

    def reserve(self, report_id):
        _check_report_id(report_id)

        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO replay_reports (report_id, status)
                    VALUES (?, 'processing')
                    """,
                    (report_id,),
                )
            return True

        except sqlite3.IntegrityError:
            # This ID has already been reserved or processed.
            return False

    def mark_processed(self, report_id):
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE replay_reports
                SET status = 'processed'
                WHERE report_id = ?
                """,
                (report_id,),
            )

            if cursor.rowcount != 1:
                raise ValueError("Report ID was not reserved.")

    def release(self, report_id):
        with self._connection() as connection:
            connection.execute(
                """
                DELETE FROM replay_reports
                WHERE report_id = ? AND status = 'processing'
                """,
                (report_id,),
            )

    def close(self):
        with self._lock:
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
