import threading
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor


class TestExecutionRace(unittest.TestCase):
    def make_state(self):
        state = AegisState()
        state.add_item("transaction")
        state.add_dependency("approval", "transaction")
        state.commit_decision("approval", {"approved": True})
        return state

    def test_evidence_update_waits_until_protected_action_finishes(self):
        state = self.make_state()
        executor = ProtectedExecutor(state)
        action_started = threading.Event()
        allow_action_to_finish = threading.Event()
        update_attempted = threading.Event()
        update_finished = threading.Event()
        action_calls = []
        errors = []

        def action():
            action_calls.append("executed")
            action_started.set()
            if not allow_action_to_finish.wait(timeout=5):
                raise TimeoutError("Test did not release protected action")
            return "completed"

        def run_executor():
            try:
                executor.execute("test_action", "approval", action)
            except Exception as exc:
                errors.append(exc)

        def update_evidence():
            update_attempted.set()
            try:
                state.set_version("transaction", 2)
            except Exception as exc:
                errors.append(exc)
            finally:
                update_finished.set()

        worker = threading.Thread(target=run_executor)
        updater = threading.Thread(target=update_evidence)
        worker.start()
        self.assertTrue(action_started.wait(timeout=5), "Action did not start")
        updater.start()
        self.assertTrue(update_attempted.wait(timeout=5), "Update did not start")

        try:
            self.assertFalse(
                update_finished.wait(timeout=0.2),
                "Evidence update should wait while the protected action holds the lock",
            )
        finally:
            allow_action_to_finish.set()
            worker.join(timeout=5)
            updater.join(timeout=5)

        self.assertFalse(worker.is_alive(), "Executor thread did not finish")
        self.assertFalse(updater.is_alive(), "Update thread did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(action_calls, ["executed"])
        self.assertTrue(update_finished.is_set())
        self.assertFalse(state.validate("approval")["valid"])

    def test_stale_decision_blocks_action(self):
        state = self.make_state()
        state.set_version("transaction", 2)
        executor = ProtectedExecutor(state)
        action_calls = []

        result = executor.execute(
            "test_action",
            "approval",
            lambda: action_calls.append("executed"),
        )

        self.assertFalse(result["executed"])
        self.assertEqual(action_calls, [])


if __name__ == "__main__":
    unittest.main()


    def test_evidence_update_can_proceed_after_action_raises(self):
        state = self.make_state()
        executor = ProtectedExecutor(state)

        def failing_action():
            raise RuntimeError("Simulated action failure")

        with self.assertRaises(RuntimeError):
            executor.execute(
                "test_action",
                "approval",
                failing_action,
            )

        # The action failed, but the state lock should have been released.
        state.set_version("transaction", 2)

        self.assertFalse(state.validate("approval")["valid"])
        
