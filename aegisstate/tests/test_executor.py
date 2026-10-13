
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor


class TestProtectedExecutor(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()

        self.state.add_item("transaction")
        self.state.add_item("risk_assessment")
        self.state.add_item("approval")

        self.state.add_dependency(
            "risk_assessment",
            "transaction",
        )

        self.state.add_dependency(
            "approval",
            "risk_assessment",
        )

        self.state.commit_decision(
            "risk_assessment",
            {"risk_score": 20},
        )

        self.state.commit_decision(
            "approval",
            {"approved": True},
        )

        self.executor = ProtectedExecutor(self.state)

    def test_valid_approval_allows_execution(self):
        result = self.executor.execute(
            action_name="transfer_transaction",
            required_decision="approval",
            action=lambda: "Transaction completed",
        )

        self.assertTrue(result["executed"])
        self.assertEqual(
            result["result"],
            "Transaction completed",
        )

    def test_invalid_approval_blocks_execution(self):
        self.state.set_version("transaction", 2)

        result = self.executor.execute(
            action_name="transfer_transaction",
            required_decision="approval",
            action=lambda: "Transaction completed",
        )

        self.assertFalse(result["executed"])

    def test_blocked_action_is_not_called(self):
        self.state.set_version("transaction", 2)

        action_called = False

        def dangerous_action():
            nonlocal action_called
            action_called = True
            return "Transaction completed"

        self.executor.execute(
            action_name="transfer_transaction",
            required_decision="approval",
            action=dangerous_action,
        )

        self.assertFalse(action_called)

    def test_execution_log_records_blocked_action(self):
        self.state.set_version("transaction", 2)

        self.executor.execute(
            action_name="transfer_transaction",
            required_decision="approval",
            action=lambda: "Transaction completed",
        )

        log = self.executor.get_execution_log()

        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["executed"])


if __name__ == "__main__":
    unittest.main()
