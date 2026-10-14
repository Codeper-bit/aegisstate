import unittest

from aegisstate.agent import Agent
from aegisstate.engine import AegisState
from aegisstate.executor import ProtectedExecutor
from aegisstate.replay_store import SQLiteReplayStore
from aegisstate.report_bridge import ReportBridge
from aegisstate.report_ingestion import (
    ReportValidationError,
    create_default_ingestor,
)
from aegisstate.report_security import (
    ReplayProtectedReportBridge,
    ReportReplayError,
)


ALLOW_D = {"risk_assessment": {"d"}}


class TestEngineRobustness(unittest.TestCase):

    def test_very_deep_chain_does_not_hit_recursion_limit(self):
        state = AegisState()
        size = 1200
        for i in range(size):
            state.add_item(f"d{i}")
        for i in range(1, size):
            state.add_dependency(f"d{i}", f"d{i - 1}")
        for i in range(size):
            self.assertTrue(
                state.commit_decision(f"d{i}", {"v": i})["committed"]
            )
        self.assertTrue(state.validate(f"d{size - 1}")["valid"])
        state.set_version("d0", 2)
        self.assertFalse(state.validate(f"d{size - 1}")["valid"])

    def test_diamond_graph_validates_quickly(self):
        # 40 stacked diamonds: exponential without memoisation.
        state = AegisState()
        state.add_item("n0")
        for i in range(40):
            a, b, c = f"a{i}", f"b{i}", f"n{i + 1}"
            state.add_dependency(a, f"n{i}")
            state.add_dependency(b, f"n{i}")
            state.add_dependency(c, a)
            state.add_dependency(c, b)
        for i in range(40):
            for name in (f"a{i}", f"b{i}", f"n{i + 1}"):
                self.assertTrue(
                    state.commit_decision(name, 1)["committed"]
                )
        self.assertTrue(state.validate("n40")["valid"])

    def test_cycles_are_rejected_and_graph_left_intact(self):
        state = AegisState()
        state.add_dependency("b", "a")
        state.add_dependency("c", "b")
        with self.assertRaises(ValueError):
            state.add_dependency("a", "c")
        self.assertEqual(state.dependencies["a"], set())
        self.assertFalse(state._has_cycle())
        with self.assertRaises(ValueError):
            state.add_dependency("a", "a")

    def test_recommitting_changed_result_invalidates_downstream(self):
        state = AegisState()
        state.add_item("evidence")
        state.add_dependency("risk", "evidence")
        state.add_dependency("approval", "risk")
        state.commit_decision("risk", {"score": 20})
        state.commit_decision("approval", {"ok": True})
        self.assertTrue(state.validate("approval")["valid"])

        # Same result: nothing changes.
        state.commit_decision("risk", {"score": 20})
        self.assertTrue(state.validate("approval")["valid"])

        # Different result, no evidence change: approval is now stale.
        state.commit_decision("risk", {"score": 95})
        self.assertFalse(state.validate("approval")["valid"])

    def test_unhashable_item_names_do_not_crash(self):
        state = AegisState()
        self.assertFalse(state.validate(["x"])["valid"])
        self.assertFalse(state.commit_decision({}, 1)["committed"])


class TestExecutorAndAgent(unittest.TestCase):

    def setUp(self):
        self.state = AegisState()
        self.state.add_item("evidence")
        self.state.add_dependency("decision", "evidence")
        self.state.commit_decision("decision", {"ok": True})

    def test_log_is_bounded(self):
        executor = ProtectedExecutor(self.state, max_log_entries=5)
        for i in range(50):
            executor.execute(f"a{i}", "decision", lambda: None)
        log = executor.get_execution_log()
        self.assertEqual(len(log), 5)
        self.assertEqual(log[-1]["action"], "a49")

    def test_invalid_log_size_rejected(self):
        for bad in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                ProtectedExecutor(self.state, max_log_entries=bad)

    def test_failed_action_is_logged_and_reraised(self):
        executor = ProtectedExecutor(self.state)

        def boom():
            raise RuntimeError("nope")

        with self.assertRaises(RuntimeError):
            executor.execute("act", "decision", boom)
        self.assertFalse(executor.get_execution_log()[-1]["executed"])

    def test_returned_result_does_not_alias_log(self):
        executor = ProtectedExecutor(self.state)
        result = executor.execute("act", "decision", lambda: 1)
        result["executed"] = False
        self.assertTrue(executor.get_execution_log()[0]["executed"])

    def test_agent_uses_valid_key(self):
        # Regression: Agent read decision["allowed"] -> KeyError.
        agent = Agent(self.state)
        self.assertTrue(agent.execute("decision"))
        self.state.set_version("evidence", 2)
        self.assertFalse(agent.execute("decision"))


class TestIngestionAndBridge(unittest.TestCase):

    def setUp(self):
        self.ingestor = create_default_ingestor()

    def report(self, **overrides):
        data = {
            "report_type": "risk_assessment",
            "decision_id": "d",
            "evidence_id": "e",
            "evidence_version": 1,
            "risk_score": 10,
        }
        data.update(overrides)
        return data

    def test_nan_and_infinity_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ReportValidationError):
                self.ingestor.validate(self.report(risk_score=bad))

    def test_bool_rejected_for_numeric_score(self):
        with self.assertRaises(ReportValidationError):
            self.ingestor.validate(self.report(risk_score=True))

    def test_bridge_rejects_unrelated_evidence(self):
        state = AegisState()
        state.add_item("e")
        state.add_item("other")
        state.add_dependency("d", "e")
        bridge = ReportBridge(
            state, allowed_decisions={"risk_assessment": {"d"}}
        )
        with self.assertRaises(ReportValidationError):
            bridge.process_report(self.report(evidence_id="other"))
        self.assertTrue(bridge.process_report(self.report())["committed"])


class TestReplayProtection(unittest.TestCase):

    def make_state(self):
        state = AegisState()
        state.add_item("e")
        state.add_dependency("d", "e")
        return state

    def report(self, rid):
        return {
            "report_id": rid,
            "report_type": "risk_assessment",
            "decision_id": "d",
            "evidence_id": "e",
            "evidence_version": 1,
            "risk_score": 10,
        }

    def test_sqlite_backed_bridge_blocks_replay_across_instances(self):
        store = SQLiteReplayStore(":memory:")
        first = ReplayProtectedReportBridge(
            self.make_state(), store, ALLOW_D)
        self.assertTrue(first.process_report(self.report("r1"))["committed"])

        second = ReplayProtectedReportBridge(
            self.make_state(), store, ALLOW_D)
        with self.assertRaises(ReportReplayError):
            second.process_report(self.report("r1"))
        store.close()

    def test_failed_reports_release_their_id(self):
        bridge = ReplayProtectedReportBridge(
            self.make_state(), allowed_decisions=ALLOW_D
        )
        bad = self.report("r2")
        bad["evidence_version"] = 9
        with self.assertRaises(ValueError):
            bridge.process_report(bad)
        self.assertTrue(bridge.process_report(self.report("r2"))["committed"])

    def test_non_mapping_rejected(self):
        bridge = ReplayProtectedReportBridge(
            self.make_state(), allowed_decisions=ALLOW_D
        )
        with self.assertRaises(ReportReplayError):
            bridge.process_report("not a report")


if __name__ == "__main__":
    unittest.main()
