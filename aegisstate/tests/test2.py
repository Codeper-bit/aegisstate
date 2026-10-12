
import unittest

from engine import AegisState
from executor import ProtectedExecutor


class TestDay10Safety(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()
        self.executor = ProtectedExecutor(self.state)

        self.state.add_item("transaction")
        self.state.add_item("risk_assessment")
        self.state.add_item("approval")
        self.state.add_item("inventory_data")
        self.state.add_item("inventory_report")
        self.state.add_item("agent_action")

        self.state.add_dependency(
            "risk_assessment", "transaction"
        )
        self.state.add_dependency(
            "approval", "risk_assessment"
        )
        self.state.add_dependency(
            "agent_action", "approval"
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
            "agent_action", {"action": "process_transaction"}
        )
        self.state.commit_decision(
            "inventory_report", {"items": 12}
        )

    def test_stale_action_is_blocked(self):
        self.state.set_version("transaction", 2)

        called = []

        result = self.executor.execute(
            "process_transaction",
            "agent_action",
            lambda: called.append(True),
        )

        self.assertFalse(result["executed"])
        self.assertEqual(called, [])

    def test_unrelated_report_remains_valid(self):
        self.state.set_version("transaction", 2)

        result = self.state.validate("inventory_report")

        self.assertTrue(result["valid"])

    def test_fresh_decisions_restore_validity(self):
        self.state.set_version("transaction", 2)

        self.state.commit_decision(
            "risk_assessment", {"risk_score": 30}
        )
        self.state.commit_decision(
            "approval", {"approved": True}
        )
        self.state.commit_decision(
            "agent_action", {"action": "process_transaction"}
        )

        result = self.state.validate("agent_action")

        self.assertTrue(result["valid"])

    def test_same_version_does_not_invalidate(self):
        result_before = self.state.validate("agent_action")

        self.state.set_version("transaction", 1)

        result_after = self.state.validate("agent_action")

        self.assertTrue(result_before["valid"])
        self.assertTrue(result_after["valid"])


if __name__ == "__main__":
    unittest.main()
