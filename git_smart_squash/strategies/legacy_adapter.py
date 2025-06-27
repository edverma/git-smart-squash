"""Adapter to use new strategy pattern with existing code."""

from typing import List, Dict, Any
from ..models import CommitGroup, Hunk as ModelHunk, ChangeType
from ..diff_parser import Hunk as LegacyHunk


class LegacyToStrategyAdapter:
    """Adapts between legacy hunk format and new strategy pattern."""

    @staticmethod
    def convert_hunks_to_model(legacy_hunks: List[LegacyHunk]) -> List[ModelHunk]:
        """Convert legacy Hunk objects to model Hunk objects."""
        model_hunks = []

        for legacy_hunk in legacy_hunks:
            # Determine change type from legacy hunk
            change_type = ChangeType.MODIFICATION  # Default
            if hasattr(legacy_hunk, "change_type"):
                try:
                    change_type = ChangeType(legacy_hunk.change_type)
                except:
                    pass

            model_hunk = ModelHunk(
                id=legacy_hunk.id,
                file_path=legacy_hunk.file_path,
                start_line=legacy_hunk.start_line,
                end_line=legacy_hunk.end_line,
                content=legacy_hunk.content,
                context=legacy_hunk.context,
                dependencies=legacy_hunk.dependencies,
                dependents=legacy_hunk.dependents,
                change_type=change_type,
            )

            model_hunks.append(model_hunk)

        return model_hunks

    @staticmethod
    def create_commit_groups(
        commit_plan: List[Dict[str, Any]], hunks_by_id: Dict[str, LegacyHunk]
    ) -> List[CommitGroup]:
        """Create CommitGroup objects from AI commit plan."""
        commit_groups = []

        for i, commit_dict in enumerate(commit_plan):
            # Get hunk IDs for this commit
            hunk_ids = commit_dict.get("hunk_ids", [])

            # Backward compatibility: handle old format with files
            if not hunk_ids and commit_dict.get("files"):
                # Convert files to hunk IDs
                file_paths = commit_dict.get("files", [])
                hunk_ids = [
                    hunk_id
                    for hunk_id, hunk in hunks_by_id.items()
                    if hunk.file_path in file_paths
                ]

            # Get the actual hunk objects
            legacy_hunks = [hunks_by_id[hid] for hid in hunk_ids if hid in hunks_by_id]

            # Convert to model hunks
            model_hunks = LegacyToStrategyAdapter.convert_hunks_to_model(legacy_hunks)

            # Create CommitGroup
            commit_group = CommitGroup(
                id=f"commit_{i}",
                message=commit_dict["message"],
                hunks=model_hunks,
                rationale=commit_dict.get("rationale", ""),
            )

            commit_groups.append(commit_group)

        return commit_groups

    @staticmethod
    def handle_remaining_hunks(
        all_hunks: List[LegacyHunk], applied_hunk_ids: set
    ) -> CommitGroup:
        """Create a CommitGroup for any remaining hunks."""
        remaining_hunks = [
            hunk for hunk in all_hunks if hunk.id not in applied_hunk_ids
        ]

        if not remaining_hunks:
            return None

        model_hunks = LegacyToStrategyAdapter.convert_hunks_to_model(remaining_hunks)

        return CommitGroup(
            id="remaining_changes",
            message="chore: remaining uncommitted changes",
            hunks=model_hunks,
            rationale="Changes not included in other commits",
        )
