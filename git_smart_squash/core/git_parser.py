"""Git operations and commit parsing."""

import subprocess
from datetime import datetime
from typing import List, Tuple, Optional
import os

from .models import Commit


class GitAnalyzer:
    """Handles Git operations and raw commit data extraction."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        
    def run_git_command(self, args: List[str]) -> str:
        """Execute a git command and return output."""
        cmd = ["git", "-C", self.repo_path] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {' '.join(cmd)}\n{e.stderr}")
    
    def is_git_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        try:
            self.run_git_command(["rev-parse", "--git-dir"])
            return True
        except RuntimeError:
            return False
    
    def get_current_branch(self) -> Optional[str]:
        """Get the current branch name."""
        try:
            # Check if we're on a branch
            branch = self.run_git_command(["symbolic-ref", "--short", "HEAD"])
            return branch
        except RuntimeError:
            # We might be in detached HEAD state
            try:
                # Get the commit hash we're on
                commit = self.run_git_command(["rev-parse", "HEAD"])
                return None  # Indicates detached HEAD
            except RuntimeError:
                return None
    
    def get_default_base_branch(self) -> str:
        """Detect the default base branch (main/master)."""
        # Try common default branch names
        for branch in ["main", "master", "develop", "development"]:
            try:
                self.run_git_command(["rev-parse", f"origin/{branch}"])
                return branch
            except RuntimeError:
                continue
        
        # If no origin, try local branches
        for branch in ["main", "master", "develop", "development"]:
            try:
                self.run_git_command(["rev-parse", branch])
                return branch
            except RuntimeError:
                continue
        
        # Default fallback
        return "main"
    
    def get_commits_between(self, base_ref: str, head_ref: str = "HEAD") -> List[Commit]:
        """Get all commits between base_ref and head_ref."""
        try:
            # Get commit hashes
            commit_hashes = self.run_git_command([
                "rev-list", 
                "--reverse",
                f"{base_ref}..{head_ref}"
            ]).split('\n')
            
            if not commit_hashes or commit_hashes == ['']:
                return []
            
            commits = []
            for commit_hash in commit_hashes:
                if commit_hash:  # Skip empty lines
                    commit = self._parse_commit(commit_hash)
                    commits.append(commit)
            
            return commits
            
        except RuntimeError as e:
            raise RuntimeError(f"Failed to get commits between {base_ref} and {head_ref}: {str(e)}")
    
    def _parse_commit(self, commit_hash: str) -> Commit:
        """Parse a single commit."""
        # Get commit metadata
        format_str = "%H%n%h%n%an%n%ae%n%at%n%P%n%s%n%b"
        output = self.run_git_command(["show", "-s", f"--format={format_str}", commit_hash])
        lines = output.split('\n')
        
        # Parse the output
        full_hash = lines[0]
        short_hash = lines[1]
        author = lines[2]
        email = lines[3]
        timestamp = datetime.fromtimestamp(int(lines[4]))
        parent_hash = lines[5] if lines[5] else ""
        subject = lines[6]
        
        # Body is everything after subject
        body_lines = lines[7:]
        body = '\n'.join(body_lines).strip()
        
        # Combine subject and body for full message
        message = subject
        if body:
            message += '\n\n' + body
        
        # Get file changes and stats
        files, insertions, deletions = self._get_commit_stats(commit_hash)
        
        # Get full diff
        diff = self._get_commit_diff(commit_hash)
        
        return Commit(
            hash=full_hash,
            short_hash=short_hash,
            author=author,
            email=email,
            timestamp=timestamp,
            message=message,
            files=files,
            insertions=insertions,
            deletions=deletions,
            diff=diff,
            parent_hash=parent_hash
        )
    
    def _get_commit_stats(self, commit_hash: str) -> Tuple[List[str], int, int]:
        """Get file changes and statistics for a commit."""
        # Get the list of changed files
        files_output = self.run_git_command([
            "show", "--name-only", "--format=", commit_hash
        ])
        files = [f for f in files_output.split('\n') if f]
        
        # Get statistics
        stats_output = self.run_git_command([
            "show", "--stat", "--format=", commit_hash
        ])
        
        # Parse insertions and deletions from the summary line
        insertions = 0
        deletions = 0
        
        for line in stats_output.split('\n'):
            if 'insertion' in line or 'deletion' in line:
                parts = line.strip().split(',')
                for part in parts:
                    if 'insertion' in part:
                        insertions = int(part.split()[0])
                    elif 'deletion' in part:
                        deletions = int(part.split()[0])
        
        return files, insertions, deletions
    
    def _get_commit_diff(self, commit_hash: str) -> str:
        """Get the full diff for a commit."""
        return self.run_git_command([
            "show", "--format=", commit_hash
        ])