"""Conflict resolution for git operations."""

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum
import re

from ..models import ConflictInfo, ConflictType, Resolution
from ..logger import logger


class ConflictResolver:
    """Handles merge conflicts during commit application."""

    def __init__(self):
        self.auto_resolution_rules = {
            ConflictType.FILE_DELETED: self._auto_resolve_file_deleted,
            ConflictType.LINE_NUMBER_SHIFT: self._auto_resolve_line_shift,
        }

    def resolve_conflict(self, conflict_info: ConflictInfo) -> Resolution:
        """Attempt automatic resolution, fall back to user intervention.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolution object with the action to take
        """
        # Try automatic resolution first
        if self.can_auto_resolve(conflict_info):
            return self.auto_resolve(conflict_info)

        # Fall back to manual resolution
        return self.manual_resolve(conflict_info)

    def can_auto_resolve(self, conflict_info: ConflictInfo) -> bool:
        """Check if conflict can be automatically resolved.

        Args:
            conflict_info: Information about the conflict

        Returns:
            True if auto-resolution is possible
        """
        # Check if we have an auto-resolution rule for this conflict type
        if conflict_info.conflict_type in self.auto_resolution_rules:
            # Additional checks based on conflict type
            if conflict_info.conflict_type == ConflictType.FILE_DELETED:
                # Can auto-resolve if changes are minor (e.g., just whitespace)
                return self._is_minor_change(conflict_info.our_changes)

            elif conflict_info.conflict_type == ConflictType.LINE_NUMBER_SHIFT:
                # Can often auto-resolve line number conflicts
                return True

        return False

    def auto_resolve(self, conflict_info: ConflictInfo) -> Resolution:
        """Automatically resolve simple conflicts.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolution with the automatic resolution
        """
        resolver_func = self.auto_resolution_rules.get(conflict_info.conflict_type)

        if resolver_func:
            return resolver_func(conflict_info)

        # Default to skipping if no resolver found
        return Resolution(action="skip", reason="No automatic resolution available")

    def manual_resolve(self, conflict_info: ConflictInfo) -> Resolution:
        """Handle manual conflict resolution.

        For now, returns a skip resolution. In a full implementation,
        this would interact with the user.

        Args:
            conflict_info: Information about the conflict

        Returns:
            Resolution based on user input
        """
        logger.warning(
            f"Manual resolution required for {conflict_info.file_path}: "
            f"{conflict_info.conflict_type.value}"
        )

        # For now, skip conflicts that can't be auto-resolved
        return Resolution(
            action="skip", reason="Manual resolution not implemented - skipping"
        )

    def _auto_resolve_file_deleted(self, conflict_info: ConflictInfo) -> Resolution:
        """Auto-resolve file deletion conflicts."""
        if self._is_minor_change(conflict_info.our_changes):
            # If changes are minor, accept the deletion
            return Resolution(
                action="use_theirs",
                reason="Accepting file deletion - changes were minor",
            )
        else:
            # If changes are significant, keep the file
            return Resolution(
                action="use_ours", reason="Keeping file - changes were significant"
            )

    def _auto_resolve_line_shift(self, conflict_info: ConflictInfo) -> Resolution:
        """Auto-resolve line number shift conflicts."""
        # Try to merge the changes
        merged_content = self._attempt_three_way_merge(
            conflict_info.base_content,
            conflict_info.our_changes,
            conflict_info.their_changes,
        )

        if merged_content:
            return Resolution(
                action="manual",
                content=merged_content,
                reason="Successfully merged with line number adjustments",
            )
        else:
            return Resolution(
                action="skip", reason="Could not automatically merge line shifts"
            )

    def _is_minor_change(self, content: Optional[str]) -> bool:
        """Check if changes are minor (whitespace, comments, etc)."""
        if not content:
            return True

        # Remove whitespace and comments
        stripped = re.sub(r"\s+", "", content)
        stripped = re.sub(r"#.*$", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"//.*$", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)

        # If very little content remains, changes are minor
        return len(stripped) < 50

    def _attempt_three_way_merge(
        self, base: Optional[str], ours: Optional[str], theirs: Optional[str]
    ) -> Optional[str]:
        """Attempt a three-way merge of content.

        This is a simplified implementation. A full implementation would
        use more sophisticated merge algorithms.
        """
        if not all([base, ours, theirs]):
            return None

        # For now, just return None to indicate merge not possible
        # A real implementation would use diff3 or similar algorithms
        return None

    def parse_git_conflict_markers(self, content: str) -> Dict[str, str]:
        """Parse Git conflict markers from file content.

        Args:
            content: File content with conflict markers

        Returns:
            Dictionary with 'ours', 'theirs', and 'base' content
        """
        pattern = r"<<<<<<< (.+?)\n(.*?)\n=======\n(.*?)\n>>>>>>> (.+?)$"

        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            return {
                "ours_ref": match.group(1),
                "ours": match.group(2),
                "theirs": match.group(3),
                "theirs_ref": match.group(4),
            }

        return {}
