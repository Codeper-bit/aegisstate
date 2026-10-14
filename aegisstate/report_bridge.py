
from .report_ingestion import (
    ReportValidationError,
    create_default_ingestor,
)


class StaleEvidenceError(ValueError):
    """Raised when a report uses an outdated evidence version."""


class ReportBridge:
    """Validates agent reports and commits them to an AegisState.

    ``allowed_decisions`` maps each report_type to the decision IDs that
    report type may commit, e.g. ``{"approval": {"approval"}}``. By default
    a report may only commit the decision named after its own report_type.
    Without this restriction any agent could, for instance, submit a
    risk_assessment report that commits ``agent_action`` and thereby skip
    the approval step entirely.
    """

    def __init__(self, state, allowed_decisions=None):
        self.state = state
        self.ingestor = create_default_ingestor()
        self.allowed_decisions = {}

        for report_type, decisions in (allowed_decisions or {}).items():
            if isinstance(decisions, str):
                decisions = {decisions}
            self.allowed_decisions[report_type] = frozenset(decisions)

    def _decisions_allowed_for(self, report_type):
        return self.allowed_decisions.get(
            report_type, frozenset({report_type})
        )

    def process_report(self, report):
        validated = self.ingestor.validate(report)
        data = validated.data

        decision_id = data["decision_id"]
        evidence_id = data["evidence_id"]
        reported_version = data["evidence_version"]

        if decision_id not in self._decisions_allowed_for(
            validated.report_type
        ):
            raise ReportValidationError(
                f"Report type '{validated.report_type}' is not "
                f"allowed to commit decision '{decision_id}'"
            )

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
