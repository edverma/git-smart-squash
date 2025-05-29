"""AI-powered commit grouping strategy."""

import json
from typing import List, Optional, Dict, Any
from ...models import Commit, CommitGroup, GroupingConfig
from ...config.manager import ConfigManager


class AIGroupingStrategy:
    """Groups commits using AI analysis of commit messages and diffs."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.config_manager = ConfigManager()
        self.ai_config = self.config_manager.config.ai
        self.ai_provider = None
        self._initialize_ai_provider()
    
    def _initialize_ai_provider(self):
        """Initialize AI provider to avoid circular imports."""
        try:
            from ...ai.providers import get_ai_provider
            self.ai_provider = get_ai_provider(self.ai_config.provider, self.ai_config.model)
        except ImportError as e:
            print(f"Failed to initialize AI provider: {e}")
            self.ai_provider = None
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits using AI analysis."""
        if len(commits) < 2:
            return []
        
        try:
            # Prepare commit data for AI
            commit_data = self._prepare_commit_data(commits)
            
            # Get AI grouping decision
            grouping_response = self._get_ai_grouping(commit_data)
            
            # Parse AI response into CommitGroups
            if grouping_response:
                return self._parse_ai_response(commits, grouping_response)
            else:
                # Fallback: create individual groups
                return self._create_fallback_groups(commits)
                
        except Exception as e:
            print(f"AI grouping failed: {e}")
            # Fallback to individual groups
            return self._create_fallback_groups(commits)
    
    def _prepare_commit_data(self, commits: List[Commit]) -> Dict[str, Any]:
        """Prepare commit data for AI analysis."""
        commit_data = []
        
        for i, commit in enumerate(commits):
            # Truncate diff if too long (AI context limits)
            truncated_diff = commit.diff[:2000] if len(commit.diff) > 2000 else commit.diff
            
            commit_info = {
                "index": i,
                "hash": commit.short_hash,
                "message": commit.message,
                "author": commit.author,
                "timestamp": commit.timestamp.isoformat(),
                "files": commit.files,
                "insertions": commit.insertions,
                "deletions": commit.deletions,
                "diff": truncated_diff
            }
            commit_data.append(commit_info)
        
        return {
            "commits": commit_data,
            "total_commits": len(commits)
        }
    
    def _get_ai_grouping(self, commit_data: Dict[str, Any]) -> Optional[str]:
        """Send commit data to AI and get grouping decision."""
        prompt = self._build_grouping_prompt(commit_data)
        
        # Use the AI provider's generate method
        # We'll extend the base AI provider to support grouping
        if hasattr(self.ai_provider, 'generate_grouping'):
            return self.ai_provider.generate_grouping(prompt)
        else:
            # Fallback: use the commit message generation method with custom prompt
            from ...ai.base import BaseAIProvider
            
            # Create a temporary implementation
            class AIGroupingProvider(BaseAIProvider):
                def __init__(self, provider):
                    self.provider = provider
                
                def generate_commit_message(self, group):
                    return None
                
                def generate_grouping(self, prompt):
                    # This would be implemented differently for each provider
                    # For now, return None to trigger fallback
                    return None
            
            temp_provider = AIGroupingProvider(self.ai_provider)
            return temp_provider.generate_grouping(prompt)
    
    def _build_grouping_prompt(self, commit_data: Dict[str, Any]) -> str:
        """Build the prompt for AI grouping analysis."""
        prompt = f"""You are an expert at analyzing git commits and determining the best way to group related commits for squashing.

Analyze the following {commit_data['total_commits']} commits and decide how to group them. Consider:
1. Semantic relationships (related features, bug fixes, etc.)
2. File overlap and logical dependencies  
3. Temporal proximity and development flow
4. Commit message patterns and conventional commit types
5. Code changes and their relationships

COMMITS TO ANALYZE:
"""
        
        for commit in commit_data['commits']:
            prompt += f"""
--- Commit {commit['index']} ---
Hash: {commit['hash']}
Message: {commit['message']}
Author: {commit['author']}
Time: {commit['timestamp']}
Files: {', '.join(commit['files'][:5])}{'...' if len(commit['files']) > 5 else ''}
Changes: +{commit['insertions']} -{commit['deletions']}
Diff (truncated):
{commit['diff'][:500]}{'...' if len(commit['diff']) > 500 else ''}
"""
        
        prompt += """

INSTRUCTIONS:
1. Group related commits together based on logical relationships
2. Each group should represent a cohesive feature, fix, or change
3. Provide a rationale for each group explaining why commits belong together
4. Suggest appropriate commit types (feat, fix, docs, etc.) for each group
5. If commits are unrelated, they can remain as individual groups

Return your response as a JSON object with this exact structure:
{
  "groups": [
    {
      "id": "group_1", 
      "commit_indices": [0, 2, 5],
      "rationale": "These commits all work together to implement user authentication feature",
      "suggested_type": "feat",
      "suggested_scope": "auth",
      "suggested_message": "feat(auth): implement user authentication system"
    }
  ]
}

IMPORTANT: 
- Include ALL commits in exactly one group (even if some are individual groups)
- Use commit indices from the data above (0-based)
- Keep rationale concise but informative
- Return ONLY the JSON, no other text
"""
        
        return prompt
    
    def _parse_ai_response(self, commits: List[Commit], response: str) -> List[CommitGroup]:
        """Parse AI response into CommitGroup objects."""
        try:
            data = json.loads(response.strip())
            groups = []
            
            for group_data in data.get('groups', []):
                group_commits = []
                
                # Get commits by indices
                for idx in group_data.get('commit_indices', []):
                    if 0 <= idx < len(commits):
                        group_commits.append(commits[idx])
                
                if len(group_commits) > 0:  # Create groups even for single commits
                    group = self._create_commit_group(
                        group_id=group_data.get('id', f'ai_group_{len(groups)}'),
                        commits=group_commits,
                        rationale=group_data.get('rationale', 'AI-determined grouping'),
                        suggested_type=group_data.get('suggested_type', 'feat'),
                        suggested_scope=group_data.get('suggested_scope'),
                        suggested_message=group_data.get('suggested_message', '')
                    )
                    groups.append(group)
            
            return groups
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse AI response: {e}")
            return self._create_fallback_groups(commits)
    
    def _create_commit_group(self, group_id: str, commits: List[Commit], 
                           rationale: str, suggested_type: str, 
                           suggested_scope: Optional[str], suggested_message: str) -> CommitGroup:
        """Create a CommitGroup from AI analysis."""
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
        
        # Use AI-suggested message or generate fallback
        if not suggested_message and len(commits) == 1:
            suggested_message = commits[0].message
        elif not suggested_message:
            suggested_message = f"{suggested_type}: {rationale[:40]}..."
        
        return CommitGroup(
            id=group_id,
            commits=sorted_commits,
            rationale=f"ai_analysis: {rationale}",
            suggested_message=suggested_message,
            commit_type=suggested_type,
            scope=suggested_scope,
            files_touched=all_files,
            total_insertions=total_insertions,
            total_deletions=total_deletions
        )
    
    def _create_fallback_groups(self, commits: List[Commit]) -> List[CommitGroup]:
        """Create individual groups as fallback when AI fails."""
        groups = []
        
        for i, commit in enumerate(commits):
            group = self._create_commit_group(
                group_id=f'fallback_group_{i}',
                commits=[commit],
                rationale='Individual commit (AI fallback)',
                suggested_type='feat',  # Default type
                suggested_scope=None,
                suggested_message=commit.message
            )
            groups.append(group)
        
        return groups