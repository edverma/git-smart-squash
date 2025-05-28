"""Main grouping engine that combines multiple strategies."""

from typing import List, Dict, Set, Tuple
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
    
    def group_commits(self, commits: List[Commit], strategies: List[str] = None) -> Tuple[List[CommitGroup], List[str]]:
        """
        Group commits using multiple strategies and merge overlapping groups.
        
        Args:
            commits: List of commits to group
            strategies: List of strategy names to use. If None, uses all strategies.
                       Options: ['file_overlap', 'temporal', 'semantic', 'dependency']
        
        Returns:
            Tuple of (groups, warnings)
        """
        if not commits:
            return [], []
        
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
        
        # Generate warnings for potential issues
        warnings = []
        if len(ungrouped_commits) > len(commits) * 0.5:
            warnings.append(f"Many commits ({len(ungrouped_commits)}) couldn't be grouped - consider adjusting grouping thresholds")
        
        if len(merged_groups) == len(commits):
            warnings.append("No commits were grouped together - this may indicate very diverse changes")
        
        return merged_groups, warnings
    
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
        
        # Score each group
        best_group = groups[0]
        best_score = self._score_group(best_group)
        
        for group in groups[1:]:
            score = self._score_group(group)
            if score > best_score:
                best_score = score
                best_group = group
        
        return best_group
    
    def _score_group(self, group: CommitGroup) -> float:
        """Score a group based on various quality metrics."""
        score = 0.0
        
        # File overlap score (higher is better)
        file_overlap_score = self.calculate_file_overlap(group.commits)
        score += file_overlap_score * 0.4
        
        # Semantic similarity score (0.0 to 1.0)
        similarity_score = self.calculate_commit_similarity(group.commits)
        score += similarity_score * 0.3
        
        # Size penalty (too many commits in one group is bad)
        size_penalty = min(len(group.commits) / 10, 1)  # Cap at 10 commits
        score -= size_penalty * 0.2
        
        # Recency bonus (newer commits grouped together is slightly better)
        if group.commits:
            avg_age_days = sum(commit.timestamp.timestamp() for commit in group.commits) / len(group.commits)
            # Normalize to 0-1 where 1 = very recent, 0 = very old
            import time
            current_time = time.time()
            max_age_days = 30 * 24 * 60 * 60  # 30 days in seconds
            recency_score = max(0, 1 - ((current_time - avg_age_days) / max_age_days))
            score += recency_score * 0.1
        
        return score

    def calculate_file_overlap(self, commits: List[Commit]) -> float:
        """Calculate file overlap score for a group of commits."""
        if not commits:
            return 0.0
        
        # Get all files touched by any commit
        all_files = set()
        for commit in commits:
            all_files.update(commit.files)
        
        if not all_files:
            return 0.0
        
        # Calculate overlap score
        overlap_score = 0.0
        for file in all_files:
            commits_touching_file = sum(1 for commit in commits if file in commit.files)
            # Score based on how many commits touch this file
            overlap_score += (commits_touching_file - 1) / (len(commits) - 1) if len(commits) > 1 else 0
        
        # Normalize by number of files
        return overlap_score / len(all_files)

    def calculate_commit_similarity(self, commits: List[Commit]) -> float:
        """Calculate semantic similarity between commits in a group."""
        if len(commits) < 2:
            return 1.0  # Single commit is perfectly similar to itself
        
        # Simple similarity based on shared keywords in commit messages
        total_similarity = 0.0
        comparisons = 0
        
        for i in range(len(commits)):
            for j in range(i + 1, len(commits)):
                similarity = self._calculate_message_similarity(commits[i].message, commits[j].message)
                total_similarity += similarity
                comparisons += 1
        
        return total_similarity / comparisons if comparisons > 0 else 0.0

    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between two commit messages."""
        # Convert to lowercase and split into words
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        # Remove common words that don't add much meaning
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words1 = words1 - common_words
        words2 = words2 - common_words
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _find_ungrouped_commits(self, original_commits: List[Commit], groups: List[CommitGroup]) -> List[Commit]:
        """Find commits that weren't included in any group."""
        grouped_hashes = set()
        for group in groups:
            for commit in group.commits:
                grouped_hashes.add(commit.hash)
        
        ungrouped = []
        for commit in original_commits:
            if commit.hash not in grouped_hashes:
                ungrouped.append(commit)
        
        return ungrouped
    
    def _create_individual_group(self, commit: Commit, group_id: str) -> CommitGroup:
        """Create a group containing a single commit."""
        return CommitGroup(
            commits=[commit],
            rationale=f"Individual commit (no grouping opportunity found)",
            confidence=1.0,
            group_id=group_id,
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