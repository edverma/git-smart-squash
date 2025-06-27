"""Atomic operations support for git commits."""

from contextlib import contextmanager
from typing import Generator, Optional, List
import git

from ..models import CommitGroup, Result
from ..logger import logger


class AtomicCommitApplicator:
    """Ensures all-or-nothing commit application."""

    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.checkpoint: Optional[git.Commit] = None
        self.original_head = None

    @contextmanager
    def atomic_operation(self) -> Generator[None, None, None]:
        """Context manager for atomic operations.

        Usage:
            with atomic_applicator.atomic_operation():
                # Apply commits
                # If any exception occurs, will rollback
        """
        # Save current state
        self.checkpoint = self.repo.head.commit
        self.original_head = self.repo.head.ref

        try:
            logger.debug(
                f"Starting atomic operation from commit {self.checkpoint.hexsha[:8]}"
            )
            yield
            logger.debug("Atomic operation completed successfully")
        except Exception as e:
            # Rollback on any error
            logger.error(f"Error during atomic operation: {str(e)}")
            self.rollback()
            raise

    def rollback(self) -> None:
        """Rollback to checkpoint."""
        if self.checkpoint:
            logger.warning(f"Rolling back to checkpoint {self.checkpoint.hexsha[:8]}")

            # Force reset to checkpoint
            self.repo.head.reset(
                self.checkpoint, index=True, working_tree=True, hard=True
            )

            # Clean any untracked files that may have been created
            self.repo.git.clean("-fd")

            logger.info("Rollback completed")
        else:
            logger.warning("No checkpoint available for rollback")

    def apply_with_rollback(self, commits: List[CommitGroup], apply_func) -> Result:
        """Apply commits with automatic rollback on failure.

        Args:
            commits: List of commit groups to apply
            apply_func: Function that applies a single commit group

        Returns:
            Result object with success/failure status
        """
        with self.atomic_operation():
            results = []

            for i, commit in enumerate(commits):
                logger.info(f"Applying commit {i+1}/{len(commits)}: {commit.id}")

                result = apply_func(commit)
                results.append(result)

                if result.is_failure:
                    # This will trigger rollback via context manager
                    raise Exception(
                        f"Failed to apply commit {commit.id}: {result.message}"
                    )

            return Result.success(
                data=results, message=f"Successfully applied {len(commits)} commits"
            )

    def create_savepoint(self) -> str:
        """Create a savepoint that can be restored later.

        Returns:
            SHA of the savepoint commit
        """
        current_commit = self.repo.head.commit
        logger.debug(f"Created savepoint at {current_commit.hexsha[:8]}")
        return current_commit.hexsha

    def restore_savepoint(self, savepoint_sha: str) -> None:
        """Restore to a specific savepoint.

        Args:
            savepoint_sha: SHA of the commit to restore to
        """
        try:
            commit = self.repo.commit(savepoint_sha)
            self.repo.head.reset(commit, index=True, working_tree=True, hard=True)
            logger.info(f"Restored to savepoint {savepoint_sha[:8]}")
        except Exception as e:
            logger.error(f"Failed to restore savepoint: {str(e)}")
            raise
