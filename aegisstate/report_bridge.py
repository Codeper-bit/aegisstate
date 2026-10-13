
from .report_ingestion import (
    ReportValidationError,
    create_default_ingestor,
)


class StaleEvidenceError(ValueError):
    """Raised when a report uses an outdated evidence version."""


class ReportBridge:
    def __init__(self, state):
        self.state = state
        self.ingestor = create_default_ingestor()

    def process_report(self, report):
        validated = self.ingestor.validate(report)
        data = validated.data

        decision_id = data["decision_id"]
        evidence_id = data["evidence_id"]
        reported_version = data["evidence_version"]

        if decision_id not in self.state.versions:
            raise ReportValidationError(
                f"Unknown decision: {decision_id}"
            )

        if evidence_id not in self.state.versions:
            raise ReportValidationError(
                f"Unknown evidence: {evidence_id}"
            )

        # Without this check, a report could cite any unrelated evidence
        # that happens to be current and still be committed.
        if evidence_id not in self.state.dependencies[decision_id]:
            raise ReportValidationError(
                f"Evidence '{evidence_id}' is not a dependency "
                f"of decision '{decision_id}'"
            )

        current_version = self.state.versions[evidence_id]

        if reported_version != current_version:
            raise StaleEvidenceError(
                f"Report version {reported_version} is outdated; "
                f"current version is {current_version}."
            )

        return self.state.commit_decision(
            decision_id,
            result=dict(data),
        )
