
import unittest

from engine import AegisState


class TestAegisStateDay5(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()

        self.state.add_dependency(
            "risk_assessment",
            "transaction"
        )

        self.state.add_dependency(
            "approval",
            "risk_assessment"
        )

        self.state.add_dependency(
            "agent_action",
            "approval"
        )

        self.state.commit_decision(
            "risk_assessment",
            {"risk_score": 20}
        )

        self.state.commit_decision(
            "approval",
            {"approved": True}
        )

        self.state.commit_decision(
            "agent_action",
            {"action": "execute"}
        )

    def test_initial_decision_is_valid(self):
        self.assertTrue(
            self.state.validate("agent_action")["valid"]
        )

    def test_transaction_change_invalidates_chain(self):
        self.state.set_version("transaction", 2)

        self.assertFalse(
            self.state.validate("agent_action")["valid"]
        )

    def test_early_approval_commit_is_rejected(self):
        self.state.set_version("transaction", 2)

        result = self.state.commit_decision(
            "approval",
            {"approved": True}
        )

        self.assertFalse(result["committed"])

    def test_recovery_in_dependency_order(self):
        self.state.set_version("transaction", 2)

        self.assertTrue(
            self.state.commit_decision(
                "risk_assessment",
                {"risk_score": 35}
            )["committed"]
        )

        self.assertTrue(
            self.state.commit_decision(
                "approval",
                {"approved": True}
            )["committed"]
        )

        self.assertTrue(
            self.state.commit_decision(
                "agent_action",
                {"action": "execute"}
            )["committed"]
        )

        self.assertTrue(
            self.state.validate("agent_action")["valid"]
        )

    def test_none_result_is_rejected(self):
        result = self.state.commit_decision(
            "risk_assessment",
            None
        )

        self.assertFalse(result["committed"])

    def test_unknown_item_is_rejected(self):
        result = self.state.commit_decision(
            "unknown",
            {"value": 1}
        )

        self.assertFalse(result["committed"])

    def test_result_is_copied(self):
        result = {"risk_score": 20}

        self.state.commit_decision(
            "risk_assessment",
            result
        )

        result["risk_score"] = 999

        self.assertEqual(
            self.state.results["risk_assessment"],
            {"risk_score": 20}
        )

    def test_snapshot_contains_provenance(self):
        snapshot = self.state.snapshot()

        self.assertIn(
            "transaction",
            snapshot["provenance"]["risk_assessment"][
                "dependency_versions"
            ]
        )


if __name__ == "__main__":
    unittest.main()
