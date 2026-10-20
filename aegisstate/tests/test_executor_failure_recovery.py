
"""Regression tests for protected execution failure and concurrent updates."""
import threading
import unittest

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor


class TestExecutorFailureRecovery(unittest.TestCase):
    def make_state(self):
        state = AegisState()
        state.add_item("evidence")
        state.add_dependency("decision", "evidence")
        state.commit_decision("decision", {"approved": True})
        return state

    def test_action_exception_is_logged_and_lock_is_released(self):
        state = self.make_state()
        executor = ProtectedExecutor(state)

        def broken_action():
            raise RuntimeError("simulated action failure")

        with self.assertRaisesRegex(RuntimeError, "simulated action failure"):
            executor.execute("test_action", "decision", broken_action)

        log = executor.get_execution_log()
        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["executed"])
        self.assertIn("RuntimeError", log[0]["reason"])

        finished = threading.Event()

        def update():
            state.set_version("evidence", 2)
            finished.set()

        worker = threading.Thread(target=update, daemon=True)
        worker.start()

        self.assertTrue(
            finished.wait(timeout=2),
            "State lock was not released",
        )
        worker.join(timeout=2)
        self.assertFalse(state.validate("decision")["valid"])

    def test_executor_can_run_again_after_action_failure(self):
        state = self.make_state()
        executor = ProtectedExecutor(state)

        with self.assertRaises(ValueError):
            executor.execute(
                "failing_action",
                "decision",
                lambda: (_ for _ in ()).throw(
                    ValueError("expected failure")
                ),
            )

        result = executor.execute(
            "retry_action", "decision", lambda: "ok"
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["result"], "ok")

    def test_concurrent_evidence_updates_do_not_corrupt_state(self):
        state = self.make_state()
        barrier = threading.Barrier(9)
        errors = []
        errors_lock = threading.Lock()

        def update(version):
            try:
                barrier.wait(timeout=3)
                state.set_version("evidence", version)
                state.snapshot()
            except Exception as exc:
                with errors_lock:
                    errors.append(exc)

        workers = [
            threading.Thread(target=update, args=(v,))
            for v in range(2, 10)
        ]

        for worker in workers:
            worker.start()

        barrier.wait(timeout=3)

        for worker in workers:
            worker.join(timeout=5)

        self.assertTrue(
            all(not worker.is_alive() for worker in workers),
            "Worker hung",
        )
        self.assertEqual(errors, [])
        self.assertFalse(state.validate("decision")["valid"])
        self.assertEqual(
            state.snapshot()["versions"]["evidence"],
            state.versions["evidence"],
        )


if __name__ == "__main__":
    unittest.main()
                              
