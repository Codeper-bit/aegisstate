"""Demonstrate validating two different agent report shapes."""
from aegisstate.report_ingestion import ReportValidationError, create_default_ingestor


def main():
    ingestor = create_default_ingestor()
    reports = [
        ("Agent A", {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "evidence_version": 3,
            "approved": True, "agent_name": "AgentA",
            "reason": "Configured checks passed",
        }),
        ("Agent B", {
            "report_type": "approval", "decision_id": "approval_105",
            "evidence_id": "transaction_43", "evidence_version": 1,
            "approved": False,
        }),
        ("Malformed agent", {
            "report_type": "approval", "decision_id": "approval_106",
            "evidence_id": "transaction_44", "approved": True,
        }),
    ]

    for name, report in reports:
        try:
            result = ingestor.validate(report)
            print(f"{name}: ACCEPTED")
            print("  Standard fields:", result.data)
            print("  Extra fields:", result.extra_fields)
        except ReportValidationError as exc:
            print(f"{name}: REJECTED — {exc}")


if __name__ == "__main__":
    main()
