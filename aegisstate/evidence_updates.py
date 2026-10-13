
class EvidenceUpdateError(ValueError):
    """Raised when an evidence update cannot be applied."""


class TrustedEvidenceUpdater:
    """
    Records evidence updates received from a trusted application source.

    Only trusted application code should call update_evidence().
    """

    def __init__(self, state):
        self.state = state

    def update_evidence(self, evidence_id):
        # The evidence must already exist.
        if (
            not isinstance(evidence_id, str)
            or evidence_id not in self.state.versions
        ):
            raise EvidenceUpdateError(
                f"Unknown evidence: {evidence_id}"
            )

        # The application, not the agent, advances the version.
        previous_version = self.state.versions[evidence_id]
        new_version = previous_version + 1

        # AegisState handles downstream invalidation.
        self.state.set_version(evidence_id, new_version)

        return {
            "evidence_id": evidence_id,
            "previous_version": previous_version,
            "current_version": new_version,
            "updated": True,
        }
