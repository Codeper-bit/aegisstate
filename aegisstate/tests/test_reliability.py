
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor


class TestAegisStateReliability(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()

        for item in (
            "transaction",
            "risk_assessment",
            "approval",
            "inventory_data",
            "inventory_report",
        ):
            self.state.add_item(item)

        self.state.add_dependency(
            "risk_assessment", "transaction"
        )
        self.state.add_dependency(
            "approval", "risk_assessment"
        )
        self.state.add_dependency(
            "inventory_report", "inventory_data"
        )

        self.state.commit_decision(
            "risk_assessment", {"risk_score": 20}
        )
        self.state.commit_decision(
            "approval", {"approved": True}
        )
        self.state.commit_decision(
            "inventory_report", {"items_available": 120}
        )

    def test_unchanged_version_preserves_valid_approval(self):
        self.state.set_version("transaction", 1)

        result = self.state.validate("approval")

        self.assertTrue(result["valid"])

    def test_unrelated_change_preserves_approval(self):
        self.state.set_version("inventory_data", 2)

        result = self.state.validate("approval")

        self.assertTrue(result["valid"])

    def test_transaction_change_invalidates_approval(self):
        self.state.set_version("transaction", 2)

        result = self.state.validate("approval")

        self.assertFalse(result["valid"])

    def test_transaction_change_preserves_inventory_report(self):
        self.state.set_version("transaction", 2)

        result = self.state.validate("inventory_report")

        self.assertTrue(result["valid"])

    def test_stale_approval_never_calls_action(self):
        self.state.set_version("transaction", 2)

        executor = ProtectedExecutor(self.state)
        action_called = False

        def action():
            nonlocal action_called
            action_called = True
            return "Executed"

        result = executor.execute(
            "execute_transaction",
            "approval",
            action,
        )

        self.assertFalse(result["executed"])
        self.assertFalse(action_called)


if __name__ == "__main__":
    unittest.main()
