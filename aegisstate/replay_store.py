import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

MAX_REPORT_ID_LENGTH = 128

# Strict ASCII allow-list. Anything looser lets an attacker replay the same
# report under a visually identical ID (trailing space, zero-width
# character, NUL byte, look-alike Unicode letter) and defeat replay
# protection. Covers UUIDs, ULIDs, hex digests and typical prefixed IDs.
_REPORT_ID_PATTERN = re.compile(
    r"[A-Za-z0-9._:\-]{1,%d}" % MAX_REPORT_ID_LENGTH
)


def validate_report_id(report_id):
    """Return the ID if acceptable, otherwise raise ValueError."""
    if not isinstance(report_id, str) or not _REPORT_ID_PATTERN.fullmatch(
        report_id
    ):
        raise ValueError(
            "report_id must be 1-%d characters using only letters, "
            "digits, '.', '_', ':' or '-'." % MAX_REPORT_ID_LENGTH
        )

    return report_id


def _require_operator_confirmation(confirmed_not_committed):
    if confirmed_not_committed is not True:
        raise ValueError(
            "Confirm that the decision was not committed "
            "before recovering this report."
        )


class InMemoryReplayStore:
    """Replay storage that lasts only while the process is running.

    Every reserved ID is remembered for the life of the process. Evicting
    old IDs would re-open the door to replay attacks, so use
    SQLiteReplayStore (and prune it deliberately) for long-running services.
    """

    def __init__(self):
        self._status = {}
        self._lock = threading.Lock()

    def reserve(self, report_id):
        validate_report_id(report_id)

        with self._lock:
            if report_id in self._status:
                return False

            self._status[report_id] = "processing"
            return True

    def mark_processed(self, report_id):
        with self._lock:
            if report_id not in self._status:
                raise ValueError("Report ID was not reserved.")

            self._status[report_id] = "processed"

    def get_status(self, report_id):
        """Return 'processing', 'processed', or None if unknown."""
        validate_report_id(report_id)

        with self._lock:
            return self._status.get(report_id)

    def recover_abandoned(
        self,
        report_id,
        *,
        confirmed_not_committed=False,
    ):
        """
        Release a stuck reservation only after an operator
        confirms that the decision was not committed.
        """
        _require_operator_confirmation(confirmed_not_committed)
        validate_report_id(report_id)

        with self._lock:
            if self._status.get(report_id) != "processing":
                raise ValueError(
                    "Report is not reserved for processing."
                )

            del self._status[report_id]

        return True

    def release(self, report_id):
        # Only unfinished reservations can be released; a processed
        # report must keep blocking replays.
        with self._lock:
            if self._status.get(report_id) == "processing":
                del self._status[report_id]

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

    File-backed databases are restricted to the current user where the OS
    supports it, because the file records every accepted report ID.
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

        if self._memory_connection is None:
            try:
                os.chmod(self.database_path, 0o600)
            except OSError:
                pass  # Best effort; not supported on every filesystem.

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
        validate_report_id(report_id)

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

    def get_status(self, report_id):
        """Return 'processing', 'processed', or None if unknown."""
        validate_report_id(report_id)

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT status
                FROM replay_reports
                WHERE report_id = ?
                """,
                (report_id,),
            ).fetchone()

        return row[0] if row else None

    def recover_abandoned(
        self,
        report_id,
        *,
        confirmed_not_committed=False,
    ):
        """
        Release a stuck reservation only after an operator
        confirms that the decision was not committed.

        A crash between reserve() and the end of processing leaves the ID
        'processing' forever. That fails closed (the report cannot be
        replayed), but a legitimate retry stays blocked until an operator
        verifies the decision was never committed and calls this.
        """
        _require_operator_confirmation(confirmed_not_committed)
        validate_report_id(report_id)

        with self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM replay_reports
                WHERE report_id = ? AND status = 'processing'
                """,
                (report_id,),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    "Report is not reserved for processing."
                )

        return True

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
