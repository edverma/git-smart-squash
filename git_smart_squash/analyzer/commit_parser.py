"""Git command wrapper for parsing commits and extracting metadata."""

import subprocess
import re
from datetime import datetime
from typing import List, Optional
from ..models import Commit


class GitCommitParser:
    """Handles parsing of git commits and extraction of metadata."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
    
    def get_commits_between(self, base_ref: str = "main", head_ref: str = "HEAD") -> List[Commit]:
        """Get all commits between base_ref and head_ref."""
        try:
            # Get commit hashes in the range
            cmd = ["git", "-C", self.repo_path, "rev-list", f"{base_ref}..{head_ref}", "--reverse"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            commit_hashes = result.stdout.strip().split('\n')
            
            if not commit_hashes or commit_hashes == ['']:
                return []
            
            commits = []
            for commit_hash in commit_hashes:
                commit = self._parse_commit(commit_hash.strip())
                if commit:
                    commits.append(commit)
            
            return commits
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get commits: {e.stderr}")
    
    def _parse_commit(self, commit_hash: str) -> Optional[Commit]:
        """Parse a single commit and return Commit object."""
        try:
            # Get commit metadata
            cmd = [
                "git", "-C", self.repo_path, "show", "--no-patch", 
                "--format=%H|%h|%an|%ae|%at|%s|%P", commit_hash
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            metadata = result.stdout.strip().split('|')
            
            if len(metadata) < 6:
                return None
            
            full_hash = metadata[0]
            short_hash = metadata[1]
            author = metadata[2]
            email = metadata[3]
            timestamp = datetime.fromtimestamp(int(metadata[4]))
            message = metadata[5]
            parent_hash = metadata[6] if len(metadata) > 6 else ""
            
            # Get file changes and diff stats
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
                parent_hash=parent_hash.split()[0] if parent_hash else ""
            )
            
        except subprocess.CalledProcessError:
            return None
    
    def _get_commit_stats(self, commit_hash: str) -> tuple[List[str], int, int]:
        """Get file changes and diff statistics for a commit."""
        try:
            # Get file list
            cmd = ["git", "-C", self.repo_path, "show", "--name-only", "--format=", commit_hash]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
            
            # Get diff stats
            cmd = ["git", "-C", self.repo_path, "show", "--stat", "--format=", commit_hash]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            stats_output = result.stdout.strip()
            
            insertions = 0
            deletions = 0
            
            # Parse the final line that contains total stats
            lines = stats_output.split('\n')
            if lines:
                last_line = lines[-1]
                # Look for patterns like "2 files changed, 10 insertions(+), 5 deletions(-)"
                insertion_match = re.search(r'(\d+) insertion', last_line)
                deletion_match = re.search(r'(\d+) deletion', last_line)
                
                if insertion_match:
                    insertions = int(insertion_match.group(1))
                if deletion_match:
                    deletions = int(deletion_match.group(1))
            
            return files, insertions, deletions
            
        except subprocess.CalledProcessError:
            return [], 0, 0
    
    def _get_commit_diff(self, commit_hash: str) -> str:
        """Get the full diff for a commit."""
        try:
            cmd = ["git", "-C", self.repo_path, "show", "--format=", commit_hash]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError:
            return ""
    
    def get_current_branch(self) -> str:
        """Get the current branch name."""
        try:
            cmd = ["git", "-C", self.repo_path, "branch", "--show-current"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "HEAD"
    
    def get_default_base_branch(self) -> str:
        """Try to determine the default base branch (main, master, develop)."""
        branches_to_try = ["main", "master", "develop"]
        
        for branch in branches_to_try:
            try:
                cmd = ["git", "-C", self.repo_path, "rev-parse", "--verify", f"refs/heads/{branch}"]
                subprocess.run(cmd, capture_output=True, check=True)
                return branch
            except subprocess.CalledProcessError:
                continue
        
        # Fallback to main if none found
        return "main"
    
    def is_git_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        try:
            cmd = ["git", "-C", self.repo_path, "rev-parse", "--git-dir"]
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False