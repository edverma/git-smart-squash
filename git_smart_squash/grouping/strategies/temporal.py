"""Temporal proximity-based grouping strategy."""

from typing import List
from datetime import timedelta
from ...models import Commit, CommitGroup, GroupingConfig
from ...analyzer.metadata_extractor import MetadataExtractor
from ...analyzer.diff_analyzer import DiffAnalyzer
from ..utils import extract_scope_from_files


class TemporalGrouping:
    """Groups commits based on temporal proximity."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.metadata_extractor = MetadataExtractor()
        self.diff_analyzer = DiffAnalyzer()
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits based on time windows."""
        if not commits:
            return []
        
        # Use the metadata extractor to group by time window
        time_groups = self.metadata_extractor.group_by_time_window(
            commits, self.config.time_window
        )
        
        # Convert to CommitGroup objects
        groups = []
        for i, group_commits in enumerate(time_groups):
            if len(group_commits) > 1:  # Only create groups with multiple commits
                group = self._create_commit_group(f"temporal_group_{i}", group_commits)
                groups.append(group)
        
        return groups
    
    def _create_commit_group(self, group_id: str, commits: List[Commit]) -> CommitGroup:
        """Create a CommitGroup from a list of temporally related commits."""
        if not commits:
            raise ValueError("Cannot create group from empty commit list")
        
        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        
        # Calculate time span
        time_span = sorted_commits[-1].timestamp - sorted_commits[0].timestamp
        
        # Calculate aggregated stats
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Determine primary commit type
        commit_types = [self.diff_analyzer.analyze_change_type(c) for c in commits]
        # Use most common type, or the type from the largest commit
        primary_type = max(set(commit_types), key=commit_types.count)
        
        # Generate rationale
        minutes = int(time_span.total_seconds() / 60)
        if minutes < 60:
            time_desc = f"{minutes} minutes"
        else:
            hours = minutes / 60
            time_desc = f"{hours:.1f} hours"
        
        rationale = f"temporal_proximity: {len(commits)} commits within {time_desc}"
        
        # Generate basic message
        if len(commits) <= 3:
            # For small groups, try to summarize the messages
            unique_types = list(set(commit_types))
            if len(unique_types) == 1:
                suggested_message = f"{primary_type}: Multiple related changes"
            else:
                suggested_message = f"{primary_type}: Combined changes across {len(all_files)} files"
        else:
            suggested_message = f"{primary_type}: Batch update ({len(commits)} commits)"
        
        # Extract scope from files
        scope = extract_scope_from_files(all_files)
        
        return CommitGroup(
            id=group_id,
            commits=sorted_commits,
            rationale=rationale,
            suggested_message=suggested_message,
            commit_type=primary_type,
            scope=scope,
            files_touched=all_files,
            total_insertions=total_insertions,
            total_deletions=total_deletions
        )
    
