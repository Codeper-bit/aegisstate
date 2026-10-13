import unittest

from aegisstate.report_ingestion import (
    ReportIngestor, ReportSchema, FieldRule, ReportValidationError,
    create_default_ingestor,
)


class ReportIngestionTests(unittest.TestCase):
    def setUp(self):
        self.ingestor = create_default_ingestor()

    def test_accepts_extra_fields(self):
        report = {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "evidence_version": 3,
            "approved": True, "agent_name": "RiskAgent", "confidence": 0.95,
        }
        result = self.ingestor.validate(report)
        self.assertEqual(result.extra_fields["agent_name"], "RiskAgent")
        self.assertEqual(result.extra_fields["confidence"], 0.95)

    def test_rejects_missing_required_field(self):
        report = {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "approved": True,
        }
        with self.assertRaisesRegex(ReportValidationError, "evidence_version"):
            self.ingestor.validate(report)

    def test_optional_risk_score_may_be_missing(self):
        report = {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "evidence_version": 3,
            "approved": True,
        }
        self.assertNotIn("risk_score", self.ingestor.validate(report).data)

    def test_rejects_wrong_type(self):
        report = {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "evidence_version": 3,
            "approved": "yes",
        }
        with self.assertRaisesRegex(ReportValidationError, "approved"):
            self.ingestor.validate(report)

    def test_rejects_boolean_as_version(self):
        report = {
            "report_type": "approval", "decision_id": "approval_104",
            "evidence_id": "transaction_42", "evidence_version": True,
            "approved": True,
        }
        with self.assertRaisesRegex(ReportValidationError, "evidence_version"):
            self.ingestor.validate(report)

    def test_rejects_out_of_range_risk_score(self):
        report = {
            "report_type": "risk_assessment", "decision_id": "risk_104",
            "evidence_id": "transaction_42", "evidence_version": 3,
            "risk_score": 120,
        }
        with self.assertRaisesRegex(ReportValidationError, "risk_score"):
            self.ingestor.validate(report)

    def test_rejects_unknown_report_type(self):
        with self.assertRaisesRegex(ReportValidationError, "Unsupported"):
            self.ingestor.validate({"report_type": "unknown"})

    def test_can_register_strict_schema(self):
        strict = ReportIngestor()
        strict.register_schema(ReportSchema(
            report_type="simple", fields={"name": FieldRule(str)},
            allow_extra_fields=False,
        ))
        with self.assertRaisesRegex(ReportValidationError, "Unknown fields"):
            strict.validate({"report_type": "simple", "name": "Agent A", "extra": "no"})


if __name__ == "__main__":
    unittest.main()
