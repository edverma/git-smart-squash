"""File overlap-based grouping strategy."""

from typing import List, Set, Dict
from ...models import Commit, CommitGroup, GroupingConfig
from ...analyzer.diff_analyzer import DiffAnalyzer
from ..utils import extract_scope_from_files


class FileOverlapGrouping:
    """Groups commits based on file overlap using graph-based clustering."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.diff_analyzer = DiffAnalyzer()
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits based on file overlap."""
        if not commits:
            return []
        
        # Build file-commit adjacency graph
        file_to_commits = self._build_file_commit_graph(commits)
        
        # Find connected components (groups of commits that share files)
        commit_groups = self._find_connected_components(commits, file_to_commits)
        
        # Convert to CommitGroup objects
        groups = []
        for i, group_commits in enumerate(commit_groups):
            if len(group_commits) >= 1:  # Only create groups with at least 1 commit
                group = self._create_commit_group(f"file_group_{i}", group_commits, "file_overlap")
                groups.append(group)
        
        return groups
    
    def _build_file_commit_graph(self, commits: List[Commit]) -> Dict[str, List[Commit]]:
        """Build a mapping from files to commits that modify them."""
        file_to_commits = {}
        
        for commit in commits:
            for file_path in commit.files:
                if file_path not in file_to_commits:
                    file_to_commits[file_path] = []
                file_to_commits[file_path].append(commit)
        
        return file_to_commits
    
    def _find_connected_components(self, commits: List[Commit], file_to_commits: Dict[str, List[Commit]]) -> List[List[Commit]]:
        """Find connected components in the commit-file graph."""
        visited = set()
        components = []
        commit_to_index = {commit.hash: i for i, commit in enumerate(commits)}
        
        def dfs(commit: Commit, component: List[Commit]):
            if commit.hash in visited:
                return
            
            visited.add(commit.hash)
            component.append(commit)
            
            # Find all commits that share files with this commit
            for file_path in commit.files:
                if file_path in file_to_commits:
                    for related_commit in file_to_commits[file_path]:
                        if related_commit.hash not in visited:
                            # Check if there's sufficient file overlap
                            overlap = self.diff_analyzer.calculate_file_overlap(commit, related_commit)
                            if overlap >= (self.config.min_file_overlap / max(len(commit.files), len(related_commit.files), 1)):
                                dfs(related_commit, component)
        
        for commit in commits:
            if commit.hash not in visited:
                component = []
                dfs(commit, component)
                if component:
                    components.append(component)
        
        return components
    
    def _create_commit_group(self, group_id: str, commits: List[Commit], rationale: str) -> CommitGroup:
        """Create a CommitGroup from a list of commits."""
        if not commits:
            raise ValueError("Cannot create group from empty commit list")
        
        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        
        # Calculate aggregated stats
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Determine primary commit type based on the largest commit or most recent
        primary_commit = max(commits, key=lambda c: c.insertions + c.deletions)
        commit_type = DiffAnalyzer.analyze_change_type(primary_commit)
        
        # Generate a basic message (will be improved by AI later)
        if len(commits) == 1:
            suggested_message = commits[0].message
        else:
            file_summary = f"Update {len(all_files)} files"
            if len(all_files) <= 3:
                file_summary = f"Update {', '.join(sorted(all_files))}"
            suggested_message = f"{commit_type}: {file_summary}"
        
        # Extract scope from files (e.g., if all files are in src/auth/, scope could be "auth")
        scope = extract_scope_from_files(all_files)
        
        return CommitGroup(
            id=group_id,
            commits=sorted_commits,
            rationale=f"{rationale}: {len(commits)} commits modify overlapping files",
            suggested_message=suggested_message,
            commit_type=commit_type,
            scope=scope,
            files_touched=all_files,
            total_insertions=total_insertions,
            total_deletions=total_deletions
        )
    
