"""Base strategy interface for commit application."""

from abc import ABC, abstractmethod
from typing import List
from ..models import CommitGroup, Result


class CommitApplicationStrategy(ABC):
    """Abstract base class for commit application strategies."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    @abstractmethod
    def apply_commits(self, commit_groups: List[CommitGroup]) -> Result:
        """Apply a list of commit groups to the repository.

        Args:
            commit_groups: List of CommitGroup objects to apply

        Returns:
            Result object indicating success/failure and any conflicts
        """
        pass

    @abstractmethod
    def validate_environment(self) -> Result:
        """Validate that the environment is suitable for this strategy.

        Returns:
            Result object indicating if environment is valid
        """
        pass
