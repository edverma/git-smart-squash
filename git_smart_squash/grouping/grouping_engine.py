"""Main grouping engine that combines multiple strategies."""

from typing import List, Dict, Set
from ..models import Commit, CommitGroup, GroupingConfig
from .strategies.file_overlap import FileOverlapGrouping
from .strategies.temporal import TemporalGrouping
from .strategies.semantic import SemanticGrouping
from .strategies.dependency import DependencyGrouping


class GroupingEngine:
    """Combines multiple grouping strategies to create optimal commit groups."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.file_overlap_grouping = FileOverlapGrouping(config)
        self.temporal_grouping = TemporalGrouping(config)
        self.semantic_grouping = SemanticGrouping(config)
        self.dependency_grouping = DependencyGrouping(config)
    
    def group_commits(self, commits: List[Commit], strategies: List[str] = None) -> List[CommitGroup]:
        """
        Group commits using multiple strategies and merge overlapping groups.
        
        Args:
            commits: List of commits to group
            strategies: List of strategy names to use. If None, uses all strategies.
                       Options: ['file_overlap', 'temporal', 'semantic', 'dependency']
        """
        if not commits:
            return []
        
        if strategies is None:
            strategies = ['file_overlap', 'temporal', 'semantic', 'dependency']
        
        # Run individual grouping strategies
        all_groups = []
        
        if 'file_overlap' in strategies:
            file_groups = self.file_overlap_grouping.group_commits(commits)
            all_groups.extend(file_groups)
        
        if 'temporal' in strategies:
            temporal_groups = self.temporal_grouping.group_commits(commits)
            all_groups.extend(temporal_groups)
        
        if 'semantic' in strategies:
            semantic_groups = self.semantic_grouping.group_commits(commits)
            all_groups.extend(semantic_groups)
        
        if 'dependency' in strategies:
            dependency_groups = self.dependency_grouping.group_commits(commits)
            all_groups.extend(dependency_groups)
        
        # Deduplicate groups that contain the same commits
        merged_groups = self._deduplicate_groups(all_groups)
        
        # Ensure all commits are accounted for
        ungrouped_commits = self._find_ungrouped_commits(commits, merged_groups)
        
        # Add individual groups for ungrouped commits
        for i, commit in enumerate(ungrouped_commits):
            individual_group = self._create_individual_group(commit, f"individual_{i}")
            merged_groups.append(individual_group)
        
        # Sort groups by timestamp of first commit
        merged_groups.sort(key=lambda g: g.commits[0].timestamp)
        
        return merged_groups
    
    def _deduplicate_groups(self, groups: List[CommitGroup]) -> List[CommitGroup]:
        """Remove duplicate groups and select the best one for each set of commits."""
        if not groups:
            return []
        
        # Group by commit signature (set of commit hashes)
        signature_to_groups = {}
        for group in groups:
            signature = frozenset(commit.hash for commit in group.commits)
            if signature not in signature_to_groups:
                signature_to_groups[signature] = []
            signature_to_groups[signature].append(group)
        
        # Select the best group for each signature
        deduplicated = []
        for signature, candidate_groups in signature_to_groups.items():
            if len(candidate_groups) == 1:
                deduplicated.append(candidate_groups[0])
            else:
                # Select the best group using existing logic
                best_group = self._select_best_group(candidate_groups)
                deduplicated.append(best_group)
        
        return deduplicated
    
    
    def _select_best_group(self, groups: List[CommitGroup]) -> CommitGroup:
        """Select the best group from overlapping groups based on quality metrics."""
        if len(groups) == 1:
            return groups[0]
        
        # Priority order: dependency > file_overlap > semantic > temporal
        strategy_priority = ['dependency', 'file_overlap', 'semantic', 'temporal']
        
        for strategy in strategy_priority:
            for group in groups:
                if strategy in group.rationale:
                    return group
        
        # Fallback to the group with most commits
        return max(groups, key=lambda g: len(g.commits))
    
    def _find_ungrouped_commits(self, all_commits: List[Commit], groups: List[CommitGroup]) -> List[Commit]:
        """Find commits that are not part of any group."""
        grouped_hashes = set()
        for group in groups:
            for commit in group.commits:
                grouped_hashes.add(commit.hash)
        
        ungrouped = []
        for commit in all_commits:
            if commit.hash not in grouped_hashes:
                ungrouped.append(commit)
        
        return ungrouped
    
    def _create_individual_group(self, commit: Commit, group_id: str) -> CommitGroup:
        """Create a group for a single commit."""
        from ..analyzer.diff_analyzer import DiffAnalyzer
        
        diff_analyzer = DiffAnalyzer()
        commit_type = diff_analyzer.analyze_change_type(commit)
        
        return CommitGroup(
            id=group_id,
            commits=[commit],
            rationale="individual: single commit with no clear relationships",
            suggested_message=commit.message,
            commit_type=commit_type,
            scope="",
            files_touched=set(commit.files),
            total_insertions=commit.insertions,
            total_deletions=commit.deletions
        )
    
    def analyze_grouping_quality(self, groups: List[CommitGroup]) -> Dict[str, any]:
        """Analyze the quality of the grouping results."""
        if not groups:
            return {'quality_score': 0}
        
        total_commits = sum(len(g.commits) for g in groups)
        groups_with_multiple = sum(1 for g in groups if len(g.commits) > 1)
        
        # Calculate compression ratio
        compression_ratio = (total_commits - len(groups)) / total_commits if total_commits > 0 else 0
        
        # Calculate average group size
        avg_group_size = total_commits / len(groups) if groups else 0
        
        # Count strategy usage
        strategy_usage = {}
        for group in groups:
            for strategy in ['file_overlap', 'temporal', 'semantic', 'dependency']:
                if strategy in group.rationale:
                    strategy_usage[strategy] = strategy_usage.get(strategy, 0) + 1
        
        # Quality score (0-1)
        quality_score = 0
        quality_score += compression_ratio * 0.4  # Grouping effectiveness
        quality_score += min(avg_group_size / 5, 1) * 0.3  # Reasonable group sizes
        quality_score += (groups_with_multiple / len(groups)) * 0.3  # Actual grouping occurred
        
        return {
            'quality_score': quality_score,
            'total_commits': total_commits,
            'total_groups': len(groups),
            'compression_ratio': compression_ratio,
            'avg_group_size': avg_group_size,
            'groups_with_multiple_commits': groups_with_multiple,
            'strategy_usage': strategy_usage
        }