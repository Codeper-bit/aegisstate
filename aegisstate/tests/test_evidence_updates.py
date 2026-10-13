
import unittest

from aegisstate.engine import AegisState
from aegisstate.evidence_updates import (
    EvidenceUpdateError,
    TrustedEvidenceUpdater,
)


class TestTrustedEvidenceUpdater(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()
        self.state.add_item("transaction", version=1)
        self.state.add_item("risk_assessment")
        self.state.add_dependency(
            "risk_assessment", "transaction"
        )

        self.updater = TrustedEvidenceUpdater(self.state)

    def test_update_advances_version(self):
        result = self.updater.update_evidence("transaction")

        self.assertEqual(result["previous_version"], 1)
        self.assertEqual(result["current_version"], 2)
        self.assertEqual(self.state.versions["transaction"], 2)

    def test_update_invalidates_dependent_decision(self):
        self.state.commit_decision(
            "risk_assessment",
            {"risk_score": 20},
        )

        self.updater.update_evidence("transaction")

        self.assertFalse(
            self.state.validate("risk_assessment")["valid"]
        )

    def test_unknown_evidence_is_rejected(self):
        with self.assertRaises(EvidenceUpdateError):
            self.updater.update_evidence("missing_transaction")


if __name__ == "__main__":
    unittest.main()
