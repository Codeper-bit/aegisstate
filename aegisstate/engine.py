class AegisState:
    def __init__(self):
        # Each item records the items it depends on.
        self.dependencies = {}

        # Stores the current version of each item.
        self.versions = {}

        # Stores decisions that have become outdated.
        self.invalidated = set()

    def add_item(self, item, version=1):
        """Register an item in the dependency graph."""

        if not isinstance(item, str) or not item:
            raise ValueError("Item must be a non-empty string.")

        if not isinstance(version, int) or version < 1:
            raise ValueError("Version must be an integer >= 1.")

        self.dependencies.setdefault(item, set())
        self.versions.setdefault(item, version)

    def add_dependency(self, item, depends_on):
        """Record that one item depends on another."""

        if item == depends_on:
            raise ValueError("An item cannot depend on itself.")

        self.add_item(item)
        self.add_item(depends_on)

        self.dependencies[item].add(depends_on)

        # Reject relationships that create dependency cycles.
        if self._has_cycle():
            self.dependencies[item].remove(depends_on)
            raise ValueError(
                "This dependency would create a cycle."
            )

    def _has_cycle(self):
        """Check whether the graph contains a cycle."""

        visiting = set()
        visited = set()

        def visit(node):
            if node in visiting:
                return True

            if node in visited:
                return False

            visiting.add(node)

            for dependency in self.dependencies.get(node, set()):
                if visit(dependency):
                    return True

            visiting.remove(node)
            visited.add(node)

            return False

        return any(
            visit(node)
            for node in list(self.dependencies)
        )

    def _descendants(self, changed_item):
        """Find every direct and indirect dependant."""

        affected = set()
        to_check = [changed_item]

        while to_check:
            current = to_check.pop()

            for item, dependencies in self.dependencies.items():

                if (
                    current in dependencies
                    and item not in affected
                ):
                    affected.add(item)
                    to_check.append(item)

        return affected

    def set_version(self, item, version):
        """Update an item's version and automatically
        invalidate all dependent decisions.
        """

        if not isinstance(version, int) or version < 1:
            raise ValueError(
                "Version must be an integer >= 1."
            )

        if item not in self.versions:
            self.add_item(item)

        old_version = self.versions[item]

        # Nothing changed, so no invalidation is needed.
        if old_version == version:
            return set()

        self.versions[item] = version

        # Invalidate every downstream dependant.
        affected = self._descendants(item)

        self.invalidated.update(affected)

        return affected

    def validate(self, item):
        """Check an item and its entire dependency chain."""

        if item not in self.versions:
            return {
                "allowed": False,
                "reason": f"Unknown item: {item}"
            }

        if item in self.invalidated:
            return {
                "allowed": False,
                "reason": (
                    f"{item} is invalidated "
                    "and must be refreshed."
                )
            }

        for dependency in sorted(
            self.dependencies.get(item, set())
        ):

            result = self.validate(dependency)

            if not result["allowed"]:
                return {
                    "allowed": False,
                    "reason": (
                        f"{item} depends on invalid item "
                        f"'{dependency}': {result['reason']}"
                    )
                }

        return {
            "allowed": True,
            "reason": (
                f"{item} and its dependencies are valid."
            )
        }

    def refresh(self, item, new_version=None):
        """Refresh a decision after its dependencies
        have been checked.
        """

        if item not in self.versions:
            return {
                "allowed": False,
                "reason": f"Unknown item: {item}"
            }

        # All dependencies must be valid first.
        for dependency in sorted(
            self.dependencies.get(item, set())
        ):

            result = self.validate(dependency)

            if not result["allowed"]:
                return {
                    "allowed": False,
                    "reason": (
                        f"Cannot refresh {item}: "
                        f"dependency '{dependency}' "
                        "is not valid."
                    )
                }

        # Optionally record a new decision version.
        if new_version is not None:

            if (
                not isinstance(new_version, int)
                or new_version < 1
            ):
                raise ValueError(
                    "Version must be an integer >= 1."
                )

            old_version = self.versions[item]

            self.versions[item] = new_version

            # A changed decision can invalidate its dependants.
            if old_version != new_version:

                affected = self._descendants(item)
                self.invalidated.update(affected)

        self.invalidated.discard(item)

        return {
            "allowed": True,
            "reason": f"{item} refreshed successfully."
        }

    def snapshot(self):
        """Return a readable snapshot of the engine state."""

        return {
            "versions": dict(
                sorted(self.versions.items())
            ),

            "dependencies": {
                item: sorted(dependencies)
                for item, dependencies
                in sorted(self.dependencies.items())
            },

            "invalidated": sorted(self.invalidated)
        }
