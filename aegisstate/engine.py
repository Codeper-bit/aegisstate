class AegisState:
    def __init__(self):
        self.dependencies = {}
        self.versions = {}
        self.invalidated = set()
        self.provenance = {}

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

        # Do not invalidate anything if the relationship
        # already exists.
        if depends_on in self.dependencies[item]:
            return

        self.dependencies[item].add(depends_on)

        # Roll back the relationship if it creates a cycle.
        if self._has_cycle():
            self.dependencies[item].remove(depends_on)

            raise ValueError(
                "Circular dependency detected"
            )

        # The item's meaning may have changed because
        # its dependency set changed.
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
            if item not in visited:
                if visit(item):
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

        # No change means no new invalidation.
        if self.versions[item] == version:
            return []

        self.versions[item] = version

        affected = self._descendants(item)

        self.invalidated.update(affected)

        return sorted(affected)

    def record_decision(self, item):
        if item not in self.dependencies:
            return {
                "recorded": False,
                "reason": "Unknown item"
            }

        # A decision can only be recorded if every
        # dependency is currently valid.
        for dependency in sorted(
            self.dependencies[item]
        ):
            result = self.validate(dependency)

            if not result["valid"]:
                return {
                    "recorded": False,
                    "reason": (
                        f"Dependency '{dependency}' "
                        "is invalid"
                    )
                }

        evidence_versions = {
            dependency: self.versions[dependency]
            for dependency in sorted(
                self.dependencies[item]
            )
        }

        self.provenance[item] = evidence_versions
        self.invalidated.discard(item)

        return {
            "recorded": True,
            "item": item,
            "based_on": evidence_versions
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
            result = self.validate(dependency)

            if not result["valid"]:
                return {
                    "valid": False,
                    "reason": (
                        f"Dependency '{dependency}' "
                        "is invalid"
                    )
                }

        # A decision with dependencies needs recorded
        # provenance before it can be trusted.
        if dependencies and item not in self.provenance:
            return {
                "valid": False,
                "reason": "Missing decision provenance"
            }

        recorded = self.provenance.get(item, {})

        for dependency in dependencies:
            if (
                recorded.get(dependency)
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
            "provenance": {
                item: dict(evidence)
                for item, evidence
                in self.provenance.items()
            }
        }
