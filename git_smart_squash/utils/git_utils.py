"""Git utility functions shared across the application."""

import subprocess
from typing import List


class GitCommandExecutor:
    """Shared utility for executing git commands."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
    
    def run_git_command(self, args: List[str]) -> str:
        """Execute a git command and return stdout."""
        cmd = ["git", "-C", self.repo_path] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}")
    
    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        try:
            self.run_git_command(["rev-parse", "--git-dir"])
            return True
        except RuntimeError:
            return False
    
    def get_default_base_branch(self) -> str:
        """Get the default base branch (main, master, develop, etc.)."""
        for branch in ["main", "master", "develop", "development"]:
            try:
                self.run_git_command(["rev-parse", f"origin/{branch}"])
                return branch
            except RuntimeError:
                continue
        raise RuntimeError("No default branch found")