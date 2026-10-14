from collections.abc import Mapping

from .replay_store import InMemoryReplayStore, validate_report_id
from .report_bridge import ReportBridge


class ReportReplayError(ValueError):
    """Raised when a report is missing an ID or is replayed."""


class ReplayProtectedReportBridge:
    """
    Rejects duplicate report IDs before delegating to ReportBridge.

    The report ID is reserved BEFORE processing, so two concurrent
    submissions of the same report cannot both pass. If processing fails,
    the reservation is released so a corrected report can be retried.

    By default replay history lives in memory for this process only; pass a
    SQLiteReplayStore to make it survive restarts.

    Security note: replay protection is only as strong as the authenticity
    of the report_id. Reports (including their ID) should be authenticated
    upstream, for example with an HMAC or signature, before reaching here.
    """

    def __init__(
        self, state, replay_store=None, allowed_decisions=None
    ):
        self.bridge = ReportBridge(
            state, allowed_decisions=allowed_decisions
        )
        self.replay_store = (
            replay_store
            if replay_store is not None
            else InMemoryReplayStore()
        )

    def process_report(self, report):
        if not isinstance(report, Mapping):
            raise ReportReplayError("Report must be a mapping.")

        # Work on one private snapshot so the ID that is reserved is
        # exactly the ID that is processed, even if the caller's object
        # is mutated from another thread in the meantime.
        report = dict(report)

        try:
            report_id = validate_report_id(report.get("report_id"))
        except ValueError as exc:
            raise ReportReplayError(
                f"A valid report_id is required. {exc}"
            ) from None

        if not self.replay_store.reserve(report_id):
            raise ReportReplayError(
                f"Report already processed: {report_id}"
            )

        try:
            result = self.bridge.process_report(report)

            # An engine refusal (e.g. an invalid dependency) is a failure
            # too: free the ID so the report can be retried.
            if not result.get("committed", False):
                self.replay_store.release(report_id)
                return result

            self.replay_store.mark_processed(report_id)
            return result

        except BaseException:
            self.replay_store.release(report_id)
            raise
