
from statistics import median
from time import perf_counter

from aegisstate.engine import AegisState


GRAPH_SIZES = (100, 500, 1000)
TRIALS = 7
VALIDATIONS_PER_TRIAL = 200


def build_chain(size):
    state = AegisState()

    for i in range(size):
        state.add_item(f"decision_{i}")

    for i in range(1, size):
        state.add_dependency(
            f"decision_{i}",
            f"decision_{i - 1}",
        )

    for i in range(size):
        state.commit_decision(
            f"decision_{i}",
            {"value": i},
        )

    return state


def benchmark_validation(size):
    state = build_chain(size)
    target = f"decision_{size - 1}"
    trial_times = []

    # Warm-up: exclude initial execution effects.
    state.validate(target)

    for _ in range(TRIALS):
        start = perf_counter()

        for _ in range(VALIDATIONS_PER_TRIAL):
            result = state.validate(target)
            if not result["valid"]:
                raise RuntimeError("Expected a valid decision")

        elapsed = perf_counter() - start
        trial_times.append(elapsed / VALIDATIONS_PER_TRIAL)

    return median(trial_times) * 1000


def benchmark_invalidation(size):
    trial_times = []

    for trial in range(TRIALS):
        # Build a fresh graph outside the timed section.
        state = build_chain(size)

        start = perf_counter()
        state.set_version("decision_0", trial + 2)
        elapsed = perf_counter() - start

        trial_times.append(elapsed * 1000)

    return median(trial_times)


def main():
    print("\n=== AEGISSTATE SCALING BENCHMARK ===")
    print(f"Trials per measurement: {TRIALS}")
    print(f"Validations per trial: {VALIDATIONS_PER_TRIAL}")
    print("Times are medians; milliseconds (ms).\n")

    for size in GRAPH_SIZES:
        validation_ms = benchmark_validation(size)
        invalidation_ms = benchmark_invalidation(size)

        print(f"Dependency chain size: {size}")
        print(f"Median validation time: {validation_ms:.3f} ms")
        print(f"Median root-change invalidation: {invalidation_ms:.3f} ms")
        print()


if __name__ == "__main__":
    main()
