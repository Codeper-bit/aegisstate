
import unittest

from engine import AegisState


class TestAegisStateDay4(unittest.TestCase):

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
            "approval",
            "account_status"
        )

        self.state.add_dependency(
            "approval",
            "account_balance"
        )

        self.state.add_dependency(
            "agent_action",
            "approval"
        )

        self.state.add_dependency(
            "inventory_report",
            "inventory_data"
        )

        # Record initial decisions in dependency order.
        for item in [
            "risk_assessment",
            "approval",
            "agent_action",
            "inventory_report"
        ]:
            result = self.state.record_decision(item)
            self.assertTrue(result["recorded"])

    def test_initial_action_is_valid(self):
        self.assertTrue(
            self.state.validate("agent_action")["valid"]
        )

    def test_balance_change_invalidates_approval(self):
        self.state.set_version(
            "account_balance",
            2
        )

        self.assertFalse(
            self.state.validate("approval")["valid"]
        )

    def test_invalidation_propagates_to_action(self):
        self.state.set_version(
            "account_balance",
            2
        )

        self.assertFalse(
            self.state.validate("agent_action")["valid"]
        )

    def test_unrelated_report_remains_valid(self):
        self.state.set_version(
            "account_balance",
            2
        )

        self.assertTrue(
            self.state.validate("inventory_report")["valid"]
        )

    def test_unrelated_risk_assessment_remains_valid(self):
        self.state.set_version(
            "account_balance",
            2
        )

        self.assertTrue(
            self.state.validate("risk_assessment")["valid"]
        )

    def test_circular_dependency_is_rejected(self):
        with self.assertRaises(ValueError):
            self.state.add_dependency(
                "transaction",
                "agent_action"
            )

        # The rejected relationship must not remain.
        self.assertNotIn(
            "agent_action",
            self.state.dependencies["transaction"]
        )

    def test_duplicate_dependency_is_ignored(self):
        before = set(
            self.state.dependencies["approval"]
        )

        self.state.add_dependency(
            "approval",
            "account_balance"
        )

        self.assertEqual(
            before,
            self.state.dependencies["approval"]
        )

    def test_same_version_does_not_invalidate(self):
        affected = self.state.set_version(
            "account_balance",
            1
        )

        self.assertEqual(affected, [])

        self.assertTrue(
            self.state.validate("agent_action")["valid"]
        )

    def test_invalid_version_is_rejected(self):
        with self.assertRaises(ValueError):
            self.state.set_version(
                "account_balance",
                0
            )

    def test_unknown_item_is_invalid(self):
        self.assertFalse(
            self.state.validate("unknown")["valid"]
        )


if __name__ == "__main__":
    unittest.main()
