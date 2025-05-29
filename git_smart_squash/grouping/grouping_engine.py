"""Main grouping engine using AI-powered commit analysis."""

from typing import List, Dict, Set, Tuple
from ..models import Commit, CommitGroup, GroupingConfig
from .strategies.ai_grouping import AIGroupingStrategy


class GroupingEngine:
    """Uses AI-powered analysis to create optimal commit groups."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.ai_grouping = AIGroupingStrategy(config)
    
    def group_commits(self, commits: List[Commit], strategies: List[str] = None) -> Tuple[List[CommitGroup], List[str]]:
        """
        Group commits using AI-powered analysis.
        
        Args:
            commits: List of commits to group
            strategies: Ignored - AI grouping is always used
        
        Returns:
            Tuple of (groups, warnings)
        """
        if not commits:
            return [], []
        
        # Use AI grouping strategy
        try:
            ai_groups = self.ai_grouping.group_commits(commits)
            
            # Sort groups by timestamp of first commit
            ai_groups.sort(key=lambda g: g.commits[0].timestamp)
            
            # Generate warnings
            warnings = []
            
            # Check if AI grouping was effective
            grouped_commits = sum(len(g.commits) for g in ai_groups)
            if grouped_commits != len(commits):
                warnings.append(f"AI grouping processed {grouped_commits}/{len(commits)} commits")
            
            single_commit_groups = sum(1 for g in ai_groups if len(g.commits) == 1)
            if single_commit_groups == len(ai_groups) and len(ai_groups) > 1:
                warnings.append("No commits were grouped together - consider using a different AI model or check commit relationships")
            
            return ai_groups, warnings
            
        except Exception as e:
            # Fallback: create individual groups
            warnings = [f"AI grouping failed: {e}. Using individual groups as fallback."]
            fallback_groups = []
            for i, commit in enumerate(commits):
                group = self._create_individual_group(commit, f"fallback_{i}")
                fallback_groups.append(group)
            
            return fallback_groups, warnings
    
    
    def _create_individual_group(self, commit: Commit, group_id: str) -> CommitGroup:
        """Create a group containing a single commit."""
        return CommitGroup(
            id=group_id,
            commits=[commit],
            rationale="individual commit (no grouping opportunity found)",
            suggested_message=commit.message,
            commit_type="feat",  # Default type
            scope=None,
            files_touched=set(commit.files),
            total_insertions=commit.insertions,
            total_deletions=commit.deletions
        )
    
    def analyze_grouping_quality(self, groups: List[CommitGroup]) -> Dict[str, any]:
        """Analyze the quality of the AI grouping results."""
        if not groups:
            return {'quality_score': 0}
        
        total_commits = sum(len(g.commits) for g in groups)
        groups_with_multiple = sum(1 for g in groups if len(g.commits) > 1)
        
        # Calculate compression ratio
        compression_ratio = (total_commits - len(groups)) / total_commits if total_commits > 0 else 0
        
        # Calculate average group size
        avg_group_size = total_commits / len(groups) if groups else 0
        
        # Count AI vs fallback groups
        ai_groups = sum(1 for g in groups if 'ai_analysis' in g.rationale)
        fallback_groups = len(groups) - ai_groups
        
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
            'ai_groups': ai_groups,
            'fallback_groups': fallback_groups,
            'ai_success_rate': ai_groups / len(groups) if groups else 0
        }