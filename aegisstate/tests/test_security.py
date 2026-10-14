import os
import pickle
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path

from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor
from aegisstate.replay_store import (
    InMemoryReplayStore,
    SQLiteReplayStore,
    validate_report_id,
)
from aegisstate.report_bridge import ReportBridge
from aegisstate.report_ingestion import ReportValidationError
from aegisstate.report_security import (
    ReplayProtectedReportBridge,
    ReportReplayError,
)


def workflow():
    state = AegisState()
    for name in ("transaction", "risk_assessment", "approval", "agent_action"):
        state.add_item(name)
    state.add_dependency("risk_assessment", "transaction")
    state.add_dependency("approval", "risk_assessment")
    state.add_dependency("agent_action", "approval")
    return state


def risk_report(**overrides):
    data = {
        "report_type": "risk_assessment",
        "decision_id": "risk_assessment",
        "evidence_id": "transaction",
        "evidence_version": 1,
        "risk_score": 5,
    }
    data.update(overrides)
    return data


class TestAuthorizationBypass(unittest.TestCase):

    def test_report_cannot_commit_a_decision_of_another_type(self):
        state = workflow()
        bridge = ReportBridge(state)
        bridge.process_report(risk_report(risk_score=99))
        bridge.process_report({
            "report_type": "approval",
            "decision_id": "approval",
            "evidence_id": "risk_assessment",
            "evidence_version": 1,
            "approved": False,  # denied
        })

        forged = risk_report(
            decision_id="agent_action",
            evidence_id="approval",
            risk_score=1,
        )
        with self.assertRaises(ReportValidationError):
            bridge.process_report(forged)

        self.assertNotIn("agent_action", state.results)
        self.assertFalse(state.validate("agent_action")["valid"])

    def test_allowed_decisions_policy_can_be_widened_explicitly(self):
        state = workflow()
        bridge = ReportBridge(
            state, allowed_decisions={"risk_assessment": "risk_assessment"}
        )
        self.assertTrue(
            bridge.process_report(risk_report())["committed"]
        )


class TestReplayIdHardening(unittest.TestCase):

    def test_lookalike_ids_are_rejected(self):
        for bad in (
            "r1 ", " r1", "r1\n", "r1\x00", "r1\u200b", "\u0433\u0031",
            "a/b", "a b", "A" * 129, "", None, 7, b"r1",
        ):
            with self.assertRaises(ValueError, msg=repr(bad)):
                validate_report_id(bad)

    def test_normal_ids_are_accepted(self):
        for good in (
            "r1", "report-001", "550e8400-e29b-41d4-a716-446655440000",
            "svc:agent.7_run", "A" * 128,
        ):
            self.assertEqual(validate_report_id(good), good)

    def test_both_stores_refuse_oversized_ids(self):
        for store in (InMemoryReplayStore(), SQLiteReplayStore(":memory:")):
            with self.assertRaises(ValueError):
                store.reserve("A" * 5_000_000)

    def test_bridge_reports_bad_ids_as_replay_errors(self):
        bridge = ReplayProtectedReportBridge(workflow())
        for bad in ("r1 ", "\u0433\u0031", "x" * 500):
            with self.assertRaises(ReportReplayError):
                bridge.process_report(risk_report(report_id=bad))

    def test_reserved_id_is_the_one_processed_despite_mutation(self):
        state = workflow()
        bridge = ReplayProtectedReportBridge(state)
        report = risk_report(report_id="orig-1")
        self.assertTrue(bridge.process_report(report)["committed"])
        report["report_id"] = "orig-2"  # mutate afterwards
        self.assertEqual(
            bridge.replay_store.get_status("orig-1"), "processed"
        )
        self.assertIsNone(bridge.replay_store.get_status("orig-2"))


class TestStoreRecoveryParity(unittest.TestCase):

    def stores(self):
        yield InMemoryReplayStore()
        yield SQLiteReplayStore(":memory:")

    def test_status_lifecycle_and_recovery_on_both_stores(self):
        for store in self.stores():
            self.assertIsNone(store.get_status("a"))
            store.reserve("a")
            self.assertEqual(store.get_status("a"), "processing")
            with self.assertRaises(ValueError):
                store.recover_abandoned("a")
            with self.assertRaises(ValueError):
                store.recover_abandoned("a", confirmed_not_committed="yes")
            self.assertTrue(
                store.recover_abandoned("a", confirmed_not_committed=True)
            )
            self.assertTrue(store.reserve("a"))
            store.mark_processed("a")
            self.assertEqual(store.get_status("a"), "processed")
            # A processed report can never be released or recovered.
            store.release("a")
            self.assertEqual(store.get_status("a"), "processed")
            with self.assertRaises(ValueError):
                store.recover_abandoned("a", confirmed_not_committed=True)
            self.assertFalse(store.reserve("a"))

    @unittest.skipIf(os.name == "nt", "POSIX permissions only")
    def test_database_file_is_private_to_the_user(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "replay.sqlite3"
            SQLiteReplayStore(database)
            self.assertEqual(database.stat().st_mode & 0o077, 0)


class TestConcurrency(unittest.TestCase):

    def test_engine_survives_concurrent_writers_and_readers(self):
        state = AegisState()
        state.add_item("root")
        errors = []

        def writer(tag):
            for i in range(400):
                try:
                    state.add_dependency(f"{tag}_{i}", "root")
                except Exception as exc:
                    errors.append(repr(exc))

        def bumper():
            for _ in range(400):
                try:
                    state.set_version("root", state.versions["root"] + 1)
                    state.snapshot()
                except Exception as exc:
                    errors.append(repr(exc))

        threads = [threading.Thread(target=writer, args=(f"w{n}",))
                   for n in range(3)]
        threads += [threading.Thread(target=bumper) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])

    def test_only_one_of_many_concurrent_duplicates_is_accepted(self):
        state = workflow()
        bridge = ReplayProtectedReportBridge(state)
        outcomes = []

        def submit():
            try:
                bridge.process_report(risk_report(report_id="same-id"))
                outcomes.append("ok")
            except ReportReplayError:
                outcomes.append("replay")

        threads = [threading.Thread(target=submit) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(outcomes.count("ok"), 1)

    def test_state_can_still_be_copied_and_pickled(self):
        state = workflow()
        self.assertEqual(
            deepcopy(state).snapshot(), state.snapshot()
        )
        self.assertEqual(
            pickle.loads(pickle.dumps(state)).snapshot(), state.snapshot()
        )


class TestIngestionLimits(unittest.TestCase):

    def test_huge_version_is_a_clean_validation_error(self):
        bridge = ReportBridge(workflow())
        with self.assertRaises(ReportValidationError):
            bridge.process_report(risk_report(evidence_version=10**5000))

    def test_overlong_ids_are_rejected(self):
        bridge = ReportBridge(workflow())
        with self.assertRaises(ReportValidationError):
            bridge.process_report(risk_report(decision_id="x" * 10_000))


class TestExecutorMemory(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()
        self.state.add_item("evidence")
        self.state.add_dependency("decision", "evidence")
        self.state.commit_decision("decision", {"ok": True})

    def test_log_does_not_retain_action_results(self):
        executor = ProtectedExecutor(self.state)
        big = bytearray(1_000_000)
        result = executor.execute("a", "decision", lambda: big)
        self.assertIs(result["result"], big)  # caller still gets it
        self.assertNotIn("result", executor.get_execution_log()[0])

    def test_error_text_is_truncated_in_log(self):
        executor = ProtectedExecutor(self.state)

        def boom():
            raise RuntimeError("x" * 100_000)

        with self.assertRaises(RuntimeError):
            executor.execute("a", "decision", boom)
        self.assertLess(
            len(executor.get_execution_log()[0]["reason"]), 400
        )

    def test_non_callable_action_is_rejected_before_logging(self):
        executor = ProtectedExecutor(self.state)
        with self.assertRaises(TypeError):
            executor.execute("a", "decision", "not callable")
        self.assertEqual(executor.get_execution_log(), [])


if __name__ == "__main__":
    unittest.main()
