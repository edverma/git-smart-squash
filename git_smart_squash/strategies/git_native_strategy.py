"""Git-native strategy for applying commits using Git's built-in operations."""

import os
import time
import tempfile
from typing import List, Dict, Optional, Set
from pathlib import Path

import git
from git import Repo, Actor

from ..models import CommitGroup, Result, ResultStatus, ConflictInfo, ConflictType, Hunk
from ..logger import logger
from .base import CommitApplicationStrategy
from .commit_builder import CommitBuilder
from .working_directory import WorkingDirectoryManager
from .atomic_operations import AtomicCommitApplicator
from .backup_manager import BackupManager
from .conflict_resolver import ConflictResolver


class GitNativeStrategy(CommitApplicationStrategy):
    """Applies changes using Git's native commit/merge operations."""

    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self.repo = Repo(repo_path)
        self.original_branch = None
        self.temp_branches = []
        self.commit_builder = CommitBuilder(repo_path)
        self.working_dir_manager = WorkingDirectoryManager(self.repo)
        self.atomic_applicator = AtomicCommitApplicator(self.repo)
        self.backup_manager = BackupManager(self.repo)
        self.conflict_resolver = ConflictResolver()

    def validate_environment(self) -> Result:
        """Validate that Git is available and repository is valid."""
        try:
            # Check if it's a valid git repository
            if not self.repo.git_dir:
                return Result.failure("Not a valid Git repository")

            # Check Git version
            git_version = self.repo.git.version_info
            if git_version < (2, 0, 0):
                return Result.failure(
                    f"Git version {git_version} is too old. Need 2.0.0+"
                )

            return Result.success(message="Environment validated successfully")

        except Exception as e:
            return Result.failure(f"Environment validation failed: {str(e)}")

    def apply_commits(self, commit_groups: List[CommitGroup]) -> Result:
        """Apply a list of commit groups using Git native operations."""
        validation = self.validate_environment()
        if validation.is_failure:
            return validation

        # Create backup before starting
        with self.backup_manager.backup_context(prefix="gss"):
            # Use working directory manager to ensure clean state
            with self.working_dir_manager:
                try:
                    # Store original branch
                    self.original_branch = self.repo.active_branch

                    # Create temporary branch for our work
                    temp_branch_name = f"gss-temp-{int(time.time())}"

                    with self.working_dir_manager.temporary_branch(temp_branch_name):
                        # Use atomic operations for all-or-nothing application
                        result = self.atomic_applicator.apply_with_rollback(
                            commit_groups, self._apply_commit_group
                        )

                        if result.is_success:
                            # Get successful commits before leaving context
                            successful_commits = self._get_successful_commits(
                                temp_branch_name
                            )
                        else:
                            successful_commits = []

                    # Now back on original branch, cherry-pick successful commits
                    if successful_commits:
                        self._cherry_pick_commits(successful_commits)

                    return result

                except Exception as e:
                    logger.error(f"Failed to apply commits: {str(e)}")
                    # Backup will be preserved due to error
                    return Result.failure(f"Failed to apply commits: {str(e)}")

    def _apply_commit_group(self, commit_group: CommitGroup) -> Result:
        """Apply a single commit group."""
        try:
            # Build complete file states from hunks using CommitBuilder
            file_states = self.commit_builder.build_file_states_for_commit(
                commit_group.hunks
            )

            # Write all files
            for file_path, content in file_states.items():
                full_path = os.path.join(self.repo_path, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)

            # Stage all changes
            self.repo.index.add([f for f in file_states.keys()])

            # Create commit
            author = Actor(
                commit_group.author_name or "git-smart-squash",
                commit_group.author_email or "git-smart-squash@localhost",
            )

            commit = self.repo.index.commit(
                message=commit_group.message, author=author, committer=author
            )

            logger.info(
                f"Created commit {commit.hexsha[:8]} for group {commit_group.id}"
            )
            return Result.success(
                data=commit.hexsha, message=f"Applied commit group {commit_group.id}"
            )

        except Exception as e:
            logger.error(f"Failed to apply commit group {commit_group.id}: {str(e)}")
            return Result.failure(f"Failed to apply commit group: {str(e)}")

    def _get_successful_commits(self, branch_name: str) -> List[str]:
        """Get list of successful commit SHAs from temp branch."""
        try:
            # Get commits that are on temp branch but not on original branch
            commits = list(
                self.repo.iter_commits(f"{self.original_branch.name}..{branch_name}")
            )
            return [c.hexsha for c in commits]
        except Exception as e:
            logger.error(f"Failed to get successful commits: {str(e)}")
            return []

    def _cherry_pick_commits(self, commit_shas: List[str]) -> None:
        """Cherry-pick commits to current branch."""
        for sha in commit_shas:
            try:
                self.repo.git.cherry_pick(sha)
                logger.info(f"Cherry-picked commit {sha[:8]}")
            except git.GitCommandError as e:
                logger.error(f"Failed to cherry-pick {sha[:8]}: {str(e)}")

                # Check if it's a conflict
                if "conflict" in str(e).lower():
                    # Get conflicted files
                    conflicted_files = self.repo.git.diff(
                        "--name-only", "--diff-filter=U"
                    ).splitlines()

                    for file_path in conflicted_files:
                        conflict_info = ConflictInfo(
                            file_path=file_path,
                            conflict_type=ConflictType.MERGE_CONFLICT,
                            error_message=str(e),
                        )

                        # Try to resolve conflict
                        resolution = self.conflict_resolver.resolve_conflict(
                            conflict_info
                        )

                        if resolution.action == "skip":
                            # Abort cherry-pick and continue
                            try:
                                self.repo.git.cherry_pick("--abort")
                            except:
                                pass
                            continue

                # If we couldn't resolve, abort the cherry-pick
                try:
                    self.repo.git.cherry_pick("--abort")
                except:
                    pass

    def _cleanup_temp_branches(self) -> None:
        """Remove temporary branches."""
        for branch_name in self.temp_branches:
            try:
                self.repo.delete_head(branch_name, force=True)
                logger.info(f"Deleted temp branch {branch_name}")
            except Exception as e:
                logger.warning(f"Failed to delete temp branch {branch_name}: {str(e)}")
