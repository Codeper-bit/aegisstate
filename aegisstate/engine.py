from copy import deepcopy


class AegisState:
    def __init__(self):
        self.dependencies = {}
        self.versions = {}
        self.invalidated = set()
        self.provenance = {}
        self.results = {}

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

    def add_dependency(self, item, depends_on):
        if item == depends_on:
            raise ValueError(
                "An item cannot depend on itself"
            )

        self.add_item(item)
        self.add_item(depends_on)

        if depends_on in self.dependencies[item]:
            return

        self.dependencies[item].add(depends_on)

        if self._has_cycle():
            self.dependencies[item].remove(depends_on)

            raise ValueError(
                "Circular dependency detected"
            )

        affected = {item} | self._descendants(item)

        self.invalidated.update(affected)

    def _has_cycle(self):
        visiting = set()
        visited = set()

        def visit(item):
            if item in visiting:
                return True

            if item in visited:
                return False

            visiting.add(item)

            for dependency in self.dependencies.get(
                item, set()
            ):
                if visit(dependency):
                    return True

            visiting.remove(item)
            visited.add(item)

            return False

        for item in self.dependencies:
            if item not in visited and visit(item):
                return True

        return False

    def _descendants(self, changed_item):
        affected = set()
        pending = [changed_item]

        while pending:
            current = pending.pop()

            for item, dependencies in self.dependencies.items():
                if (
                    current in dependencies
                    and item not in affected
                ):
                    affected.add(item)
                    pending.append(item)

        return affected

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

    def commit_decision(self, item, result):
        """
        Commit a newly calculated decision.

        The caller must calculate the result before submitting it.
        AegisState validates dependencies and records the versions
        used to support the submitted result.

        This prototype does not independently prove that the result
        was calculated correctly.
        """

        if item not in self.dependencies:
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
        self.results[item] = deepcopy(result)

        self.provenance[item] = {
            "dependency_versions": evidence_versions,
            "item_version": self.versions[item]
        }

        self.invalidated.discard(item)

        return {
            "committed": True,
            "item": item,
            "result": deepcopy(self.results[item]),
            "provenance": deepcopy(
                self.provenance[item]
            )
        }

    def validate(self, item):
        if item not in self.dependencies:
            return {
                "valid": False,
                "reason": "Unknown item"
            }

        if item in self.invalidated:
            return {
                "valid": False,
                "reason": "Decision invalidated"
            }

        dependencies = self.dependencies[item]

        for dependency in sorted(dependencies):
            validation = self.validate(dependency)

            if not validation["valid"]:
                return {
                    "valid": False,
                    "reason": (
                        f"Dependency '{dependency}' "
                        "is invalid"
                    )
                }

        # An item with dependencies needs a committed result.
        if dependencies and item not in self.provenance:
            return {
                "valid": False,
                "reason": "Missing decision provenance"
            }

        if dependencies:
            record = self.provenance[item]

            recorded_versions = record[
                "dependency_versions"
            ]

            for dependency in dependencies:
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
