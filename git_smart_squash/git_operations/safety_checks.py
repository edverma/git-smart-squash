"""Git safety checks and backup functionality."""

import subprocess
import os
from datetime import datetime
from typing import List, Optional


class GitSafetyChecker:
    """Performs safety checks before git operations."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
    
    def perform_safety_checks(self) -> List[str]:
        """Perform all safety checks and return list of warnings/errors."""
        warnings = []
        
        # Check if we're in a git repository
        if not self._is_git_repo():
            warnings.append("Not in a git repository")
            return warnings
        
        # Check for uncommitted changes
        if self._has_uncommitted_changes():
            warnings.append("Uncommitted changes detected. Commit or stash them first.")
        
        # Check for untracked files
        untracked = self._get_untracked_files()
        if untracked:
            warnings.append(f"Untracked files found: {', '.join(untracked[:3])}{'...' if len(untracked) > 3 else ''}")
        
        # Check if on a branch (not detached HEAD)
        if self._is_detached_head():
            warnings.append("Currently in detached HEAD state. Switch to a branch first.")
        
        # Check for merge conflicts
        if self._has_merge_conflicts():
            warnings.append("Merge conflicts detected. Resolve them first.")
        
        # Check if upstream branch exists
        current_branch = self._get_current_branch()
        if current_branch and not self._has_upstream_branch(current_branch):
            warnings.append(f"Branch '{current_branch}' has no upstream. Push may be required after squashing.")
        
        return warnings
    
    def create_backup_branch(self, backup_name: Optional[str] = None) -> str:
        """Create a backup branch before performing operations."""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_branch = self._get_current_branch()
            backup_name = f"backup_{current_branch}_{timestamp}"
        
        try:
            cmd = ["git", "-C", self.repo_path, "branch", backup_name]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return backup_name
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create backup branch: {e.stderr}")
    
    def verify_git_state_unchanged(self, initial_head: str) -> bool:
        """Verify that git state hasn't changed since initial check."""
        try:
            cmd = ["git", "-C", self.repo_path, "rev-parse", "HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            current_head = result.stdout.strip()
            return current_head == initial_head
        except subprocess.CalledProcessError:
            return False
    
    def get_current_head(self) -> str:
        """Get the current HEAD commit hash."""
        try:
            cmd = ["git", "-C", self.repo_path, "rev-parse", "HEAD"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            cmd = ["git", "-C", self.repo_path, "rev-parse", "--git-dir"]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    def _has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes in working directory."""
        try:
            cmd = ["git", "-C", self.repo_path, "status", "--porcelain"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return True  # Assume changes if we can't check
    
    def _get_untracked_files(self) -> List[str]:
        """Get list of untracked files."""
        try:
            cmd = ["git", "-C", self.repo_path, "ls-files", "--others", "--exclude-standard"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            files = result.stdout.strip().split('\n')
            return [f for f in files if f]
        except subprocess.CalledProcessError:
            return []
    
    def _is_detached_head(self) -> bool:
        """Check if currently in detached HEAD state."""
        try:
            cmd = ["git", "-C", self.repo_path, "branch", "--show-current"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return not result.stdout.strip()
        except subprocess.CalledProcessError:
            return True  # Assume detached if we can't check
    
    def _has_merge_conflicts(self) -> bool:
        """Check for merge conflicts."""
        try:
            cmd = ["git", "-C", self.repo_path, "ls-files", "-u"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError:
            return False
    
    def _get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            cmd = ["git", "-C", self.repo_path, "branch", "--show-current"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def _has_upstream_branch(self, branch_name: str) -> bool:
        """Check if branch has upstream configured."""
        try:
            cmd = ["git", "-C", self.repo_path, "rev-parse", "--abbrev-ref", f"{branch_name}@{{upstream}}"]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

