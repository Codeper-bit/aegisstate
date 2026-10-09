# AegisState

AegisState is a Python prototype exploring dependency-aware
invalidation of AI-agent decisions.

## Problem

An agent may make a decision using evidence that later changes.
If the agent continues to rely on that old decision, it may
perform an action using outdated information.

## Proposed approach

AegisState records dependencies between evidence, assessments,
approvals, and actions.

When an item's version changes, the engine invalidates its
downstream dependants.

Before an action proceeds, the engine validates the action and
its dependency chain.

Unrelated decisions should remain usable.

## Current features

- Dependency graph
- Automatic invalidation after version changes
- Transitive dependency propagation
- Recursive validation
- Refresh checks
- Cycle detection
- Deterministic agent simulator
- Automated unit tests

## Technology

- Python
- Standard library only
- unittest

## Run the demonstration

```bash
python main.py