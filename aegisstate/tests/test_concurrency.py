import threading
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor


class TestExecutionRace(unittest.TestCase):
    """Diagnostic test for the validation-to-execution race.

    This test deliberately changes evidence after validation has completed
    but before ProtectedExecutor calls the action. With the current executor
    implementation, the action is expected to run. That demonstrates the
    race; it is NOT a passing safety test.
    """

    def test_action_can_run_after_evidence_changes(self):
        state = AegisState()
        state.add_item("transaction")
        state.add_dependency("approval", "transaction")
        state.commit_decision("approval", {"approved": True})

        executor = ProtectedExecutor(state)
        validation_completed = threading.Event()
        continue_execution = threading.Event()
        action_calls = []
        errors = []

        original_validate = state.validate

        def controlled_validate(item):
            result = original_validate(item)
            if item == "approval":
                validation_completed.set()
                if not continue_execution.wait(timeout=5):
                    raise TimeoutError("Timed out waiting to continue execution")
            return result

        state.validate = controlled_validate

        def action():
            action_calls.append("executed")
            return "completed"

        def run_executor():
            try:
                executor.execute(
                    action_name="test_action",
                    required_decision="approval",
                    action=action,
                )
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=run_executor)
        worker.start()

        try:
            if not validation_completed.wait(timeout=5):
                self.fail("Executor did not reach validation")
            state.set_version("transaction", 2)
        finally:
            continue_execution.set()
            worker.join(timeout=5)

        self.assertFalse(worker.is_alive(), "Executor thread did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(
            action_calls,
            ["executed"],
            "Expected to reproduce the current validation-to-execution race",
        )


if __name__ == "__main__":
    unittest.main()
