"""Validated report ingestion for AegisState.

Schema validation checks report structure, not truth. The integrating
application must establish authoritative evidence versions.
"""
from dataclasses import dataclass, field
from typing import Any, Mapping


class ReportValidationError(ValueError):
    """Raised when a report does not satisfy its registered schema."""


@dataclass(frozen=True)
class FieldRule:
    expected_type: type | tuple[type, ...]
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class ReportSchema:
    report_type: str
    fields: Mapping[str, FieldRule]
    allow_extra_fields: bool = True


@dataclass
class ValidatedReport:
    report_type: str
    data: dict[str, Any]
    extra_fields: dict[str, Any] = field(default_factory=dict)


class ReportIngestor:
    """Validates incoming agent reports against registered schemas."""

    def __init__(self) -> None:
        self._schemas: dict[str, ReportSchema] = {}

    def register_schema(self, schema: ReportSchema) -> None:
        if not isinstance(schema.report_type, str) or not schema.report_type.strip():
            raise ValueError("report_type must be a non-empty string")
        if schema.report_type in self._schemas:
            raise ValueError(f"Schema already registered: {schema.report_type}")
        self._schemas[schema.report_type] = schema

    def validate(self, report: Mapping[str, Any]) -> ValidatedReport:
        if not isinstance(report, Mapping):
            raise ReportValidationError("Report must be a JSON-like object")

        report_type = report.get("report_type")
        if not isinstance(report_type, str) or not report_type:
            raise ReportValidationError("Missing required field: report_type")

        schema = self._schemas.get(report_type)
        if schema is None:
            raise ReportValidationError(f"Unsupported report_type: {report_type}")

        for name, rule in schema.fields.items():
            if name not in report:
                if rule.required:
                    raise ReportValidationError(f"Missing required field: {name}")
                continue

            value = report[name]
            if rule.expected_type is int and isinstance(value, bool):
                raise ReportValidationError(f"Field '{name}' must be int, not bool")
            if not isinstance(value, rule.expected_type):
                expected = (
                    ", ".join(t.__name__ for t in rule.expected_type)
                    if isinstance(rule.expected_type, tuple)
                    else rule.expected_type.__name__
                )
                raise ReportValidationError(f"Field '{name}' must be of type {expected}")
            if rule.minimum is not None and value < rule.minimum:
                raise ReportValidationError(f"Field '{name}' must be >= {rule.minimum}")
            if rule.maximum is not None and value > rule.maximum:
                raise ReportValidationError(f"Field '{name}' must be <= {rule.maximum}")

        known = {"report_type", *schema.fields.keys()}
        extras = {key: value for key, value in report.items() if key not in known}
        if extras and not schema.allow_extra_fields:
            raise ReportValidationError("Unknown fields are not allowed: " + ", ".join(sorted(extras)))

        return ValidatedReport(
            report_type=report_type,
            data={key: value for key, value in report.items() if key in known},
            extra_fields=extras,
        )


def create_default_ingestor() -> ReportIngestor:
    ingestor = ReportIngestor()
    ingestor.register_schema(
        ReportSchema(
            report_type="risk_assessment",
            fields={
                "decision_id": FieldRule(str),
                "evidence_id": FieldRule(str),
                "evidence_version": FieldRule(int, minimum=1),
                "risk_score": FieldRule((int, float), minimum=0, maximum=100),
            },
        )
    )
    ingestor.register_schema(
        ReportSchema(
            report_type="approval",
            fields={
                "decision_id": FieldRule(str),
                "evidence_id": FieldRule(str),
                "evidence_version": FieldRule(int, minimum=1),
                "approved": FieldRule(bool),
                "risk_score": FieldRule((int, float), required=False, minimum=0, maximum=100),
            },
        )
    )
    return ingestor
