import unittest

from engine import AegisState


class AegisStateTests(unittest.TestCase):

    def make_state(self):
        state = AegisState()

        state.add_dependency(
            "risk_assessment",
            "transaction"
        )

        state.add_dependency(
            "approval",
            "risk_assessment"
        )

        state.add_dependency(
            "agent_action",
            "approval"
        )

        state.add_dependency(
            "other_action",
            "other_transaction"
        )

        return state

    def test_initial_actions_are_valid(self):
        state = self.make_state()

        self.assertTrue(
            state.validate("agent_action")["allowed"]
        )

        self.assertTrue(
            state.validate("other_action")["allowed"]
        )

    def test_change_invalidates_downstream_items(self):
        state = self.make_state()

        affected = state.set_version(
            "transaction",
            2
        )

        self.assertEqual(
            affected,
            {
                "risk_assessment",
                "approval",
                "agent_action"
            }
        )

        self.assertFalse(
            state.validate("agent_action")["allowed"]
        )

    def test_unrelated_action_remains_valid(self):
        state = self.make_state()

        state.set_version("transaction", 2)

        self.assertTrue(
            state.validate("other_action")["allowed"]
        )

    def test_early_refresh_is_rejected(self):
        state = self.make_state()

        state.set_version("transaction", 2)

        result = state.refresh("agent_action")

        self.assertFalse(result["allowed"])

    def test_bottom_up_refresh(self):
        state = self.make_state()

        state.set_version("transaction", 2)

        self.assertTrue(
            state.refresh(
                "risk_assessment",
                new_version=2
            )["allowed"]
        )

        self.assertTrue(
            state.refresh(
                "approval",
                new_version=2
            )["allowed"]
        )

        self.assertTrue(
            state.refresh(
                "agent_action",
                new_version=2
            )["allowed"]
        )

        self.assertTrue(
            state.validate("agent_action")["allowed"]
        )

    def test_dependency_cycles_are_rejected(self):
        state = AegisState()

        state.add_dependency(
            "approval",
            "risk_assessment"
        )

        with self.assertRaises(ValueError):
            state.add_dependency(
                "risk_assessment",
                "approval"
            )

    def test_unknown_items_are_blocked(self):
        state = self.make_state()

        self.assertFalse(
            state.validate("unknown_action")["allowed"]
        )


if __name__ == "__main__":
    unittest.main()
