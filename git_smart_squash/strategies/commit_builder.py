"""Builder for constructing complete file states from hunks."""

import os
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from ..models import Hunk, ChangeType
from ..logger import logger


class CommitBuilder:
    """Builds actual file changes instead of patches."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def build_file_state(self, file_path: str, hunks: List[Hunk]) -> str:
        """Construct the complete file content with all hunks applied.

        Args:
            file_path: Path to the file relative to repo root
            hunks: List of hunks to apply to this file

        Returns:
            The complete file content after applying all hunks
        """
        # Read current file content
        full_path = os.path.join(self.repo_path, file_path)

        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = ""

        # Sort hunks by line number (reverse order to maintain line positions)
        sorted_hunks = sorted(hunks, key=lambda h: h.start_line, reverse=True)

        # Apply each hunk
        for hunk in sorted_hunks:
            content = self.apply_hunk_to_content(content, hunk)

        return content

    def apply_hunk_to_content(self, content: str, hunk: Hunk) -> str:
        """Apply a single hunk to file content.

        This method handles the actual content transformation based on the hunk type
        and content. It's designed to work with the line-based changes.
        """
        # If hunk specifies new_content directly, use it
        if hunk.new_content is not None:
            if hunk.old_content is not None:
                # Replace old content with new content
                content = content.replace(hunk.old_content, hunk.new_content)
            else:
                # For additions or complete replacements
                if hunk.change_type == ChangeType.ADDITION:
                    content = self._insert_at_line(
                        content, hunk.new_content, hunk.start_line
                    )
                else:
                    # Complete file replacement
                    content = hunk.new_content
            return content

        # Parse diff-style content from hunk
        if hunk.content:
            return self._apply_diff_content(content, hunk)

        return content

    def _apply_diff_content(self, content: str, hunk: Hunk) -> str:
        """Apply diff-style hunk content to file."""
        lines = content.splitlines(keepends=True)

        # Parse the hunk content to extract changes
        hunk_lines = hunk.content.splitlines(keepends=True)

        # Extract additions and deletions from diff format
        additions = []
        deletions = []
        context_lines = []

        for line in hunk_lines:
            if line.startswith("+") and not line.startswith("+++"):
                additions.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                deletions.append(line[1:])
            elif line.startswith(" "):
                context_lines.append(line[1:])

        # Apply changes at the specified line range
        start = max(0, hunk.start_line - 1)  # Convert to 0-based index
        end = min(len(lines), hunk.end_line)

        # Build new content
        new_lines = lines[:start]

        # Skip deleted lines and add new lines
        current_pos = start
        for line in lines[start:end]:
            if line.rstrip("\n") not in [d.rstrip("\n") for d in deletions]:
                new_lines.append(line)
            current_pos += 1

        # Add any new lines
        for addition in additions:
            new_lines.append(addition)

        # Add remaining lines
        new_lines.extend(lines[end:])

        return "".join(new_lines)

    def _insert_at_line(self, content: str, new_content: str, line_number: int) -> str:
        """Insert content at a specific line number."""
        lines = content.splitlines(keepends=True)

        # Ensure new content ends with newline if needed
        if new_content and not new_content.endswith("\n") and lines:
            new_content += "\n"

        # Insert at the specified position
        insert_pos = max(0, min(line_number - 1, len(lines)))
        lines.insert(insert_pos, new_content)

        return "".join(lines)

    def build_file_states_for_commit(self, hunks: List[Hunk]) -> Dict[str, str]:
        """Build complete file states for all files in a commit.

        Args:
            hunks: All hunks that belong to this commit

        Returns:
            Dictionary mapping file paths to their complete content
        """
        # Group hunks by file
        hunks_by_file: Dict[str, List[Hunk]] = {}
        for hunk in hunks:
            if hunk.file_path not in hunks_by_file:
                hunks_by_file[hunk.file_path] = []
            hunks_by_file[hunk.file_path].append(hunk)

        # Build state for each file
        file_states = {}
        for file_path, file_hunks in hunks_by_file.items():
            try:
                file_states[file_path] = self.build_file_state(file_path, file_hunks)
                logger.debug(
                    f"Built state for {file_path} with {len(file_hunks)} hunks"
                )
            except Exception as e:
                logger.error(f"Failed to build state for {file_path}: {str(e)}")
                raise

        return file_states

    def validate_file_state(self, file_path: str, content: str) -> bool:
        """Validate that the file state is valid.

        Performs basic validation like checking for syntax errors in known file types.
        """
        # For now, just check that we have content
        # In the future, could add language-specific validation
        return content is not None
