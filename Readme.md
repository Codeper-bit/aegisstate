Quick Start

AegisState helps prevent AI-agent actions from relying on outdated decisions.

Installation

Clone the repository and install the package locally:

python -m pip install --no-build-isolation -e .

Run the Example

python examples/basic_usage.py

The example creates a dependency chain from transaction evidence to an agent action. When the transaction version changes, AegisState invalidates dependent decisions, and the protected executor blocks the stale action.

Run the Tests

python -m unittest discover -s aegisstate/tests -v

Run the tests from the repository root.

Core Capabilities

- Track dependencies between evidence and decisions.
- Detect stale decisions when underlying versions change.
- Invalidate affected downstream decisions.
- Preserve unrelated decisions where their dependencies remain valid.
- Block protected actions when their required decisions are invalid.