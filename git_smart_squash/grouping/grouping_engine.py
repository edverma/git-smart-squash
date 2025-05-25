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
    
    def _merge_groups(self, groups: List[CommitGroup]) -> CommitGroup:
        """Merge multiple groups into a single group."""
        if len(groups) == 1:
            return groups[0]
        
        # Collect all unique commits
        all_commits = []
        seen_hashes = set()
        for group in groups:
            for commit in group.commits:
                if commit.hash not in seen_hashes:
                    all_commits.append(commit)
                    seen_hashes.add(commit.hash)
        
        # Sort by timestamp
        all_commits.sort(key=lambda c: c.timestamp)
        
        # Combine metadata
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in all_commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Determine the best rationale and type
        best_group = self._select_best_group(groups)
        
        # Create merged group ID
        group_ids = [g.id for g in groups]
        merged_id = f"merged_{'_'.join(group_ids[:3])}"  # Limit length
        
        # Combine rationales
        rationales = [g.rationale for g in groups]
        combined_rationale = f"multiple_strategies: {'; '.join(set(rationales))}"
        
        return CommitGroup(
            id=merged_id,
            commits=all_commits,
            rationale=combined_rationale,
            suggested_message=best_group.suggested_message,
            commit_type=best_group.commit_type,
            scope=best_group.scope,
            files_touched=all_files,
            total_insertions=total_insertions,
            total_deletions=total_deletions
        )
    
    def _select_best_group(self, groups: List[CommitGroup]) -> CommitGroup:
        """Select the best group from overlapping groups based on quality metrics."""
        # Scoring criteria:
        # 1. Dependency groups are preferred (more logical)
        # 2. File overlap groups are next (concrete relationship)
        # 3. Semantic groups (content-based)
        # 4. Temporal groups (least reliable)
        
        strategy_scores = {
            'dependency': 4,
            'file_overlap': 3,
            'semantic': 2,
            'temporal': 1
        }
        
        best_group = groups[0]
        best_score = 0
        
        for group in groups:
            score = 0
            
            # Strategy preference
            for strategy, strategy_score in strategy_scores.items():
                if strategy in group.rationale:
                    score += strategy_score
                    break
            
            # Size bonus (larger groups often indicate better grouping)
            score += len(group.commits) * 0.1
            
            # Message quality bonus
            if len(group.suggested_message) > 10 and ':' in group.suggested_message:
                score += 0.5
            
            if score > best_score:
                best_score = score
                best_group = group
        
        return best_group
    
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