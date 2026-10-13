
from collections.abc import Mapping

from .report_bridge import ReportBridge


class ReportReplayError(ValueError):
    """Raised when a report is missing an ID or is replayed."""


class ReplayProtectedReportBridge:
    """
    Rejects duplicate report IDs before delegating to ReportBridge.

    Replay history is kept in memory for this process only.
    """

    def __init__(self, state):
        self.bridge = ReportBridge(state)
        self.processed_report_ids = set()

    def process_report(self, report):
        if not isinstance(report, Mapping):
            raise ReportReplayError(
                "Report must be a mapping."
            )

        report_id = report.get("report_id")

        if not isinstance(report_id, str) or not report_id.strip():
            raise ReportReplayError(
                "A non-empty report_id is required."
            )

        if report_id in self.processed_report_ids:
            raise ReportReplayError(
                f"Report already processed: {report_id}"
            )

        # Process the report first. Failed reports are not recorded.
        result = self.bridge.process_report(report)

        # Record the ID only after successful processing.
        self.processed_report_ids.add(report_id)

        return result
