
from time import perf_counter

from aegisstate.engine import AegisState


def build_chain(size=100):
    state = AegisState()

    for i in range(size):
        state.add_item(f"decision_{i}")

    for i in range(1, size):
        state.add_dependency(
            f"decision_{i}",
            f"decision_{i - 1}",
        )

    # Record decisions from the root to the final node.
    for i in range(size):
        state.commit_decision(
            f"decision_{i}",
            {"value": i},
        )

    return state


def main():
    size = 100
    repetitions = 100

    state = build_chain(size)
    final_decision = f"decision_{size - 1}"

    # Measure validation before any evidence changes.
    start = perf_counter()

    for _ in range(repetitions):
        result = state.validate(final_decision)

        if not result["valid"]:
            raise RuntimeError("Expected a valid decision")

    validation_time = (
        perf_counter() - start
    ) / repetitions

    # Build a fresh graph for the invalidation measurement.
    state = build_chain(size)

    start = perf_counter()
    state.set_version("decision_0", 2)
    invalidation_time = perf_counter() - start

    print("\n=== AEGISSTATE DAY 8 BENCHMARK ===")
    print(f"Dependency chain size: {size}")
    print(f"Validation repetitions: {repetitions}")
    print(
        f"Average validation time: "
        f"{validation_time * 1000:.3f} ms"
    )
    print(
        f"Root-change invalidation time: "
        f"{invalidation_time * 1000:.3f} ms"
    )


if __name__ == "__main__":
    main()
