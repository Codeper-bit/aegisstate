# AegisState

**Dependency-aware temporal integrity for AI-agent decisions.**

[![PyPI](https://img.shields.io/pypi/v/aegisstate.svg)](https://pypi.org/project/aegisstate/)
[![Python](https://img.shields.io/pypi/pyversions/aegisstate.svg)](https://pypi.org/project/aegisstate/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Codeper-bit/aegisstate/blob/main/LICENSE.txt)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

AI agents make decisions from evidence, and evidence changes. AegisState tracks which decisions rest on which evidence, invalidates only the decisions affected when that evidence changes, and blocks protected actions that still rely on a stale decision.

> A decision should not be treated as current merely because it was valid when it was made. Its dependencies must still support its use.

---

## The problem

Consider a payment workflow run by agents:

1. An agent receives a transaction.
2. A risk assessment is produced from it.
3. An approval is recorded from the assessment.
4. An agent acts on the approval.
5. **The transaction changes.**

The assessment and approval were reasonable when made, but they describe a transaction that no longer exists. Unless every component re-implements its own staleness checks, the agent acts on outdated reasoning.

AegisState makes those dependencies explicit and enforces them at the one place that matters: right before an action runs.

## Features

- **Dependency graph.** Declare which items depend on which, with cycle detection.
- **Targeted invalidation.** A change invalidates its downstream decisions only. Unrelated decisions stay valid.
- **Protected execution.** `ProtectedExecutor` runs an action only while its required decision is valid, and logs every outcome.
- **Provenance.** Each committed decision records the dependency versions it was built on.
- **Report ingestion.** Schema-validated agent reports, with evidence-version checks and an allow-list of decisions each report type may commit.
- **Replay protection.** Duplicate report IDs are rejected, using an in-memory or SQLite-backed store with crash recovery.
- **Thread-safe, zero dependencies.** Pure standard library, Python 3.10+.

## Installation

```bash
pip install aegisstate
```

The optional Streamlit dashboard lives in the source repository (see [Dashboard](#dashboard)).

## Quick start

```python
from aegisstate import AegisState

state = AegisState()

# Register evidence and the decisions built on it.
state.add_item("transaction", version=1)
state.add_item("risk_assessment", version=1)
state.add_item("approval", version=1)

# A downstream item depends on its upstream item.
state.add_dependency("risk_assessment", "transaction")
state.add_dependency("approval", "risk_assessment")

# Record decisions produced by your application or agent.
state.commit_decision("risk_assessment", {"risk_score": 0.2})
state.commit_decision("approval", {"approved": True})

print(state.validate("approval"))
# {'valid': True, 'reason': 'Decision is valid'}

# The underlying evidence changes.
state.set_version("transaction", 2)

print(state.validate("risk_assessment"))
# {'valid': False, 'reason': 'Decision invalidated'}
print(state.validate("approval"))
# {'valid': False, 'reason': 'Decision invalidated'}
```

`set_version` returns the sorted list of items it invalidated. AegisState does not compute risk scores or decide whether to approve anything. Your application produces the decisions; AegisState tells you whether they can still be trusted.

## Guarding actions

Route sensitive actions through `ProtectedExecutor`. If the required decision is invalid, the action never runs.

```python
from aegisstate import AegisState, ProtectedExecutor

state = AegisState()
executor = ProtectedExecutor(state)

for item in ["transaction", "risk_assessment", "approval", "agent_action"]:
    state.add_item(item)

state.add_dependency("risk_assessment", "transaction")
state.add_dependency("approval", "risk_assessment")
state.add_dependency("agent_action", "approval")

state.commit_decision("transaction", {"amount": 1000})
state.commit_decision("risk_assessment", {"risk_score": 20})
state.commit_decision("approval", {"approved": True})
state.commit_decision("agent_action", {"action": "pay"})

print(executor.execute("process_payment", "agent_action", lambda: "paid"))
# {'executed': True, 'action': 'process_payment', 'result': 'paid'}

state.set_version("transaction", 2)   # evidence changed

print(executor.execute("process_payment", "agent_action", lambda: "paid"))
# {'executed': False, 'action': 'process_payment', 'reason': 'Decision invalidated'}
```

To recover, recommit the decisions **upstream to downstream** (`risk_assessment`, then `approval`, then `agent_action`). Each one becomes valid again once its own dependencies are current, and the action is permitted again.

The execution log (`executor.get_execution_log()`) is bounded and omits action results by default, so long-running processes do not leak memory or retain sensitive output.

## API overview

| Method | Purpose |
| --- | --- |
| `add_item(item, version=1)` | Register an evidence item or decision. |
| `add_dependency(item, depends_on)` | Declare that `item` relies on `depends_on`. Raises `ValueError` on self-dependency or cycles. |
| `set_version(item, version)` | Record a new evidence version. Invalidates downstream decisions and returns their names. |
| `commit_decision(item, result)` | Record a decision and its provenance. Returns a dict with a `committed` flag. |
| `validate(item)` | Returns `{"valid": bool, "reason": str}`. |
| `snapshot()` | Returns a copy of versions, dependencies, invalidations, provenance and results. |
| `ProtectedExecutor.execute(name, decision, fn)` | Run `fn` only if `decision` is valid. |

## Trusted evidence updates

Evidence versions should advance under the application's control, not the agent's. `TrustedEvidenceUpdater` increments an existing evidence item's version and triggers downstream invalidation:

```python
from aegisstate.evidence_updates import TrustedEvidenceUpdater

updater = TrustedEvidenceUpdater(state)
updater.update_evidence("transaction")
# {'evidence_id': 'transaction', 'previous_version': 1,
#  'current_version': 2, 'updated': True}
```

Only trusted application code should call it. A version bump does not prove the new evidence is authentic.

## Agent reports and replay protection

Agents often report asynchronously and may deliver the same report twice. `ReplayProtectedReportBridge` validates each report, checks that it cites a current evidence version, and rejects duplicates.

```python
from aegisstate import AegisState
from aegisstate.report_security import ReplayProtectedReportBridge
from aegisstate.replay_store import SQLiteReplayStore

state = AegisState()
state.add_item("transaction")
state.add_item("risk_assessment")
state.add_dependency("risk_assessment", "transaction")

bridge = ReplayProtectedReportBridge(
    state, replay_store=SQLiteReplayStore("replay.db")
)

report = {
    "report_type": "risk_assessment",
    "report_id": "r-001",
    "decision_id": "risk_assessment",
    "evidence_id": "transaction",
    "evidence_version": 1,
    "risk_score": 20,
}

bridge.process_report(report)   # committed
bridge.process_report(report)   # ReportReplayError: Report already processed: r-001

state.set_version("transaction", 2)
report["report_id"] = "r-002"
bridge.process_report(report)   # StaleEvidenceError: Report version 1 is outdated
```

What the bridge enforces:

- **Schema validation:** required fields, types, ranges and length limits.
- **Allow-list of commits:** by default a report may commit only the decision named after its own `report_type`, so a `risk_assessment` report cannot commit `agent_action` and skip the approval step. Widen this with `allowed_decisions`.
- **Dependency check:** the evidence a report cites must actually be a dependency of the decision it commits.
- **Evidence freshness:** the report's evidence version must match the current version.
- **Reserve-before-process replay IDs:** concurrent duplicates cannot both pass, and a failed report releases its ID so a corrected one can be retried.

`InMemoryReplayStore` is process-local. `SQLiteReplayStore` survives restarts, and supports recovering reports abandoned by a crash.

## Performance

On a 100-decision dependency chain, validating the final decision averaged about **0.11 ms**, and invalidating the entire chain from its root took about **0.07 ms**. These figures were measured on a development sandbox, so run the benchmark on your own hardware:

```bash
python -m aegisstate.benchmark
```

## Security model and limitations

AegisState strengthens the integrity of decision-dependent workflows. It is **not** a complete security boundary.

**What it helps with**

- Detecting that tracked decisions are stale after relevant version changes.
- Leaving unrelated decisions valid.
- Blocking actions routed through `ProtectedExecutor` when their decision is invalid.
- Rejecting malformed, out-of-policy, stale and duplicate reports.

**What it does not guarantee**

- That evidence is authentic or accurate, or that an agent reasoned correctly or actually used the evidence it cites.
- That every action is protected. Code paths that bypass the executor are outside its control.
- That validation and the external side effect are atomic. A decision can go stale between the check and the action, so high-impact actions need their own coordination.
- Authentication, authorization or transport security. Authenticate reports (for example with an HMAC or signature) *before* they reach the bridge, because replay protection is only as strong as the authenticity of the report ID.
- Distributed coordination. Replay stores are single-node, and report processing and decision commits are not one atomic transaction across failures.

Combine AegisState with authentication, trusted evidence ingestion, durable storage and domain-specific safety checks.

## Dashboard

A Streamlit dashboard for exploring dependency graphs, state changes and protected execution is included in the source repository (it is not part of the PyPI package):

```bash
git clone https://github.com/Codeper-bit/aegisstate.git
cd aegisstate
pip install -e ".[dashboard]"
python -m streamlit run dashboard.py
```

It is a local development and demonstration tool, not a production monitoring service.

## Development

```bash
git clone https://github.com/Codeper-bit/aegisstate.git
cd aegisstate
pip install -e .
python -m unittest discover -s aegisstate/tests -v
```

The suite (91 tests) covers dependency invalidation, validation, protected execution, report handling, replay stores and crash recovery, concurrency and input hardening. Examples are in [`examples/`](https://github.com/Codeper-bit/aegisstate/tree/main/examples).

Issues and pull requests are welcome at [github.com/Codeper-bit/aegisstate](https://github.com/Codeper-bit/aegisstate).

## License

Released under the [MIT License](https://github.com/Codeper-bit/aegisstate/blob/main/LICENSE.txt).
