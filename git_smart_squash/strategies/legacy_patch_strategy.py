"""Legacy patch-based strategy for backward compatibility."""

import subprocess
from typing import List, Dict
from ..models import CommitGroup, Result
from ..logger import logger
from .base import CommitApplicationStrategy
from ..hunk_applicator import apply_hunks_with_fallback, reset_staging_area
from ..diff_parser import Hunk as LegacyHunk


class LegacyPatchStrategy(CommitApplicationStrategy):
    """Legacy implementation using patch application."""

    def __init__(self, repo_path: str, full_diff: str, legacy_hunks: List[LegacyHunk]):
        super().__init__(repo_path)
        self.full_diff = full_diff
        self.legacy_hunks = legacy_hunks
        self.hunks_by_id = {hunk.id: hunk for hunk in legacy_hunks}

    def validate_environment(self) -> Result:
        """Validate that git is available."""
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"], check=True, capture_output=True
            )
            return Result.success(message="Git environment validated")
        except:
            return Result.failure("Not in a git repository")

    def apply_commits(self, commit_groups: List[CommitGroup]) -> Result:
        """Apply commits using the legacy patch method."""
        validation = self.validate_environment()
        if validation.is_failure:
            return validation

        try:
            commits_created = 0
            all_applied_hunk_ids = set()
            results = []

            for group in commit_groups:
                logger.info(f"Applying commit group: {group.id}")

                # Reset staging area before each commit
                reset_staging_area()

                # Get hunk IDs from the commit group
                hunk_ids = [hunk.id for hunk in group.hunks]

                if hunk_ids:
                    try:
                        # Apply hunks using the legacy hunk applicator
                        logger.debug(
                            f"Attempting to apply {len(hunk_ids)} hunks for commit: {group.message}"
                        )
                        logger.debug(f"Hunk IDs: {hunk_ids}")

                        success = apply_hunks_with_fallback(
                            hunk_ids, self.hunks_by_id, self.full_diff
                        )

                        logger.debug(
                            f"Hunk application result: {'success' if success else 'failed'}"
                        )

                        if success:
                            # Check if there are actually staged changes
                            result = subprocess.run(
                                ["git", "diff", "--cached", "--name-only"],
                                capture_output=True,
                                text=True,
                            )

                            staged_files = result.stdout.strip()
                            logger.debug(
                                f"Staged files after hunk application: {staged_files if staged_files else 'NONE'}"
                            )

                            if staged_files:
                                # Create the commit
                                subprocess.run(
                                    ["git", "commit", "-m", group.message], check=True
                                )
                                commits_created += 1
                                all_applied_hunk_ids.update(hunk_ids)

                                logger.info(f"Created commit: {group.message}")
                                results.append(
                                    Result.success(
                                        data=group.id,
                                        message=f"Applied commit group {group.id}",
                                    )
                                )

                                # Update working directory to match the commit
                                subprocess.run(
                                    ["git", "reset", "--hard", "HEAD"], check=True
                                )

                                # Force git to refresh the working directory state
                                subprocess.run(
                                    ["git", "status"], capture_output=True, check=True
                                )
                            else:
                                logger.warning(
                                    f"No changes staged for commit: {group.message}"
                                )
                                results.append(
                                    Result.failure(
                                        f"No changes to stage for commit group {group.id}"
                                    )
                                )
                        else:
                            logger.error(
                                f"Failed to apply hunks for commit: {group.message}"
                            )
                            results.append(
                                Result.failure(
                                    f"Failed to apply hunks for commit group {group.id}"
                                )
                            )

                    except Exception as e:
                        logger.error(f"Error applying commit '{group.message}': {e}")
                        results.append(
                            Result.failure(
                                f"Error applying commit group {group.id}: {str(e)}"
                            )
                        )
                else:
                    logger.warning(f"No hunks specified for commit: {group.message}")
                    results.append(
                        Result.failure(
                            f"No hunks specified for commit group {group.id}"
                        )
                    )

            return Result.success(
                data=results,
                message=f"Applied {commits_created} commits using legacy method",
            )

        except Exception as e:
            logger.error(f"Failed to apply commits: {str(e)}")
            return Result.failure(f"Failed to apply commits: {str(e)}")
