import threading
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps


def _locked(method):
    """Run a public method while holding the instance lock.

    Without it, concurrent callers crash with ``RuntimeError: dictionary
    changed size during iteration`` and can interleave a version change
    between a validation and the commit that depends on it.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class AegisState:
    def __init__(self):
        self._lock = threading.RLock()
        self.dependencies = {}
        self.versions = {}
        self.invalidated = set()
        self.provenance = {}
        self.results = {}

    @_locked
    def add_item(self, item, version=1):
        if not isinstance(item, str) or not item:
            raise ValueError(
                "Item name must be a non-empty string"
            )

        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            raise ValueError(
                "Version must be a positive integer"
            )

        if item not in self.dependencies:
            self.dependencies[item] = set()
            self.versions[item] = version

    @_locked
    def add_dependency(self, item, depends_on):
        if item == depends_on:
            raise ValueError(
                "An item cannot depend on itself"
            )

        self.add_item(item)
        self.add_item(depends_on)

        if depends_on in self.dependencies[item]:
            return

        # The new edge item -> depends_on closes a cycle only if
        # depends_on already (transitively) depends on item.
        if self._depends_on(depends_on, item):
            raise ValueError(
                "Circular dependency detected"
            )

        self.dependencies[item].add(depends_on)

        affected = {item} | self._descendants(item)

        self.invalidated.update(affected)

    def _depends_on(self, start, target):
        """True if `start` is `target` or transitively depends on it."""
        pending = [start]
        seen = set()

        while pending:
            current = pending.pop()

            if current == target:
                return True

            if current in seen:
                continue

            seen.add(current)
            pending.extend(self.dependencies.get(current, ()))

        return False

    def _has_cycle(self):
        """Iterative cycle check (no recursion limit)."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {item: WHITE for item in self.dependencies}

        for root in self.dependencies:
            if colour[root] != WHITE:
                continue

            colour[root] = GREY
            stack = [(root, iter(self.dependencies[root]))]

            while stack:
                node, children = stack[-1]

                for child in children:
                    state = colour.get(child, BLACK)

                    if state == GREY:
                        return True

                    if state == WHITE:
                        colour[child] = GREY
                        stack.append(
                            (child, iter(self.dependencies[child]))
                        )
                        break
                else:
                    colour[node] = BLACK
                    stack.pop()

        return False

    def _descendants(self, changed_item):
        """Every item that directly or indirectly depends on the item.

        Builds the reverse edge map once (O(items + edges)) instead of
        rescanning the whole graph for every node visited.
        """
        dependents = {}

        for item, dependencies in self.dependencies.items():
            for dependency in dependencies:
                dependents.setdefault(dependency, []).append(item)

        affected = set()
        pending = [changed_item]

        while pending:
            current = pending.pop()

            for item in dependents.get(current, ()):
                if item not in affected:
                    affected.add(item)
                    pending.append(item)

        return affected

    @_locked
    def set_version(self, item, version):
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or version < 1
        ):
            raise ValueError(
                "Version must be a positive integer"
            )

        self.add_item(item)

        if self.versions[item] == version:
            return []

        self.versions[item] = version

        affected = self._descendants(item)

        self.invalidated.update(affected)

        return sorted(affected)

    @_locked
    def commit_decision(self, item, result):
        """
        Commit a newly calculated decision.

        The caller must calculate the result before submitting it.
        AegisState validates dependencies and records the versions
        used to support the submitted result.

        This prototype does not independently prove that the result
        was calculated correctly.
        """

        if not isinstance(item, str) or item not in self.dependencies:
            return {
                "committed": False,
                "reason": "Unknown item"
            }

        if result is None:
            return {
                "committed": False,
                "reason": "Decision result cannot be None"
            }

        # Check every dependency before accepting the decision.
        for dependency in sorted(self.dependencies[item]):
            validation = self.validate(dependency)

            if not validation["valid"]:
                return {
                    "committed": False,
                    "reason": (
                        f"Dependency '{dependency}' "
                        "is invalid"
                    )
                }

        # Capture the versions that support this decision.
        evidence_versions = {
            dependency: self.versions[dependency]
            for dependency in sorted(
                self.dependencies[item]
            )
        }

        # Store a copy so later changes to a mutable object
        # supplied by the caller do not silently change
        # the recorded result.
        # If this item already had a different result, anything built on
        # the old result is now stale even though no evidence version
        # changed.
        previous_result = self.results.get(item)
        result_changed = (
            item in self.results and previous_result != result
        )

        self.results[item] = deepcopy(result)

        self.provenance[item] = {
            "dependency_versions": evidence_versions,
            "item_version": self.versions[item]
        }

        self.invalidated.discard(item)

        if result_changed:
            self.invalidated.update(self._descendants(item))

        return {
            "committed": True,
            "item": item,
            "result": deepcopy(self.results[item]),
            "provenance": deepcopy(
                self.provenance[item]
            )
        }

    @contextmanager
    def validation_guard(self, item):
        """Hold the state lock while validating and using a decision.

        Evidence updates through this AegisState instance are blocked until
        the guarded operation exits. Keep guarded operations short; external
        systems still need their own transactional safeguards.
        """
        with self._lock:
            yield self.validate(item)

    @_locked
    def validate(self, item):
        if not isinstance(item, str) or item not in self.dependencies:
            return {
                "valid": False,
                "reason": "Unknown item"
            }

        # Iterative post-order walk with memoisation: no RecursionError on
        # deep chains and no repeated work on diamond-shaped graphs.
        status = {}
        in_progress = set()
        stack = [(item, False)]

        while stack:
            node, children_done = stack.pop()

            if node in status:
                continue

            if not children_done:
                if node in in_progress:
                    status[node] = {
                        "valid": False,
                        "reason": "Circular dependency detected"
                    }
                    continue

                in_progress.add(node)
                stack.append((node, True))

                for dependency in self.dependencies[node]:
                    if dependency not in status:
                        stack.append((dependency, False))

                continue

            in_progress.discard(node)
            status[node] = self._check_node(node, status)

        return status[item]

    def _check_node(self, node, status):
        """Validate one node given the status of its dependencies."""
        if node in self.invalidated:
            return {
                "valid": False,
                "reason": "Decision invalidated"
            }

        dependencies = self.dependencies[node]

        for dependency in sorted(dependencies):
            if not status[dependency]["valid"]:
                return {
                    "valid": False,
                    "reason": (
                        f"Dependency '{dependency}' "
                        "is invalid"
                    )
                }

        # An item with dependencies needs a committed result.
        if dependencies and node not in self.provenance:
            return {
                "valid": False,
                "reason": "Missing decision provenance"
            }

        if dependencies:
            recorded_versions = self.provenance[node][
                "dependency_versions"
            ]

            for dependency in sorted(dependencies):
                if (
                    recorded_versions.get(dependency)
                    != self.versions[dependency]
                ):
                    return {
                        "valid": False,
                        "reason": (
                            f"Stale evidence: "
                            f"'{dependency}' changed"
                        )
                    }

        return {
            "valid": True,
            "reason": "Decision is valid"
        }

    @_locked
    def snapshot(self):
        return {
            "versions": dict(self.versions),
            "dependencies": {
                item: sorted(dependencies)
                for item, dependencies
                in self.dependencies.items()
            },
            "invalidated": sorted(self.invalidated),
            "provenance": deepcopy(self.provenance),
            "results": deepcopy(self.results)
        }

    # Locks cannot be copied or pickled; recreate one on the new instance.
    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_lock"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = threading.RLock()
