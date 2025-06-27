"""Working directory state management for git operations."""

import git
from typing import Optional
from contextlib import contextmanager

from ..logger import logger
from ..models import Result


class WorkingDirectoryManager:
    """Manages working directory state and changes."""

    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.stash_entry: Optional[str] = None
        self.original_branch = None

    def prepare_clean_state(self) -> Result:
        """Ensure working directory is clean."""
        try:
            if self.repo.is_dirty(untracked_files=True):
                # Stash any uncommitted changes including untracked files
                logger.info("Stashing uncommitted changes")
                self.stash_entry = self.repo.git.stash(
                    "push", "-u", "-m", "git-smart-squash-backup"
                )
                logger.info(f"Created stash: {self.stash_entry}")

            return Result.success(message="Working directory prepared")

        except Exception as e:
            return Result.failure(f"Failed to prepare working directory: {str(e)}")

    def restore_state(self) -> Result:
        """Restore original working directory state."""
        try:
            if self.stash_entry:
                logger.info("Restoring stashed changes")
                self.repo.git.stash("pop")
                self.stash_entry = None

            return Result.success(message="Working directory restored")

        except Exception as e:
            logger.error(f"Failed to restore working directory: {str(e)}")
            return Result.failure(f"Failed to restore working directory: {str(e)}")

    def __enter__(self):
        """Context manager entry."""
        result = self.prepare_clean_state()
        if result.is_failure:
            raise RuntimeError(result.message)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.restore_state()

    @contextmanager
    def temporary_branch(self, branch_name: str):
        """Context manager for working on a temporary branch."""
        self.original_branch = self.repo.active_branch

        try:
            # Create and checkout temporary branch
            temp_branch = self.repo.create_head(branch_name)
            temp_branch.checkout()
            logger.info(f"Created and checked out temporary branch: {branch_name}")

            yield temp_branch

        finally:
            # Always try to return to original branch
            if self.original_branch:
                try:
                    self.original_branch.checkout()
                    logger.info(
                        f"Returned to original branch: {self.original_branch.name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to return to original branch: {str(e)}")

            # Try to delete temporary branch
            try:
                self.repo.delete_head(branch_name, force=True)
                logger.info(f"Deleted temporary branch: {branch_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to delete temporary branch {branch_name}: {str(e)}"
                )

    def ensure_file_exists(self, file_path: str) -> bool:
        """Ensure a file exists in the working directory."""
        import os

        full_path = os.path.join(self.repo.working_dir, file_path)
        return os.path.exists(full_path)

    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)
