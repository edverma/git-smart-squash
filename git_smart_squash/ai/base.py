"""Base class for AI providers."""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import CommitGroup


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, model: str):
        self.model = model
    
    @abstractmethod
    def generate_commit_message(self, group: CommitGroup) -> Optional[str]:
        """Generate a commit message for the given group."""
        pass
    
    def _build_prompt(self, group: CommitGroup) -> str:
        """Build a prompt for the AI model based on the commit group."""
        prompt = f"""Generate a conventional commit message for the following group of related commits.

Context:
- Commit type: {group.commit_type}
- Scope: {group.scope or 'none'}
- Files changed: {len(group.files_touched)} files
- Changes: +{group.total_insertions} -{group.total_deletions}

Original commits:
"""
        
        for commit in group.commits:
            prompt += f"- {commit.short_hash}: {commit.message}\n"
        
        prompt += f"""
Key files modified:
{', '.join(list(group.files_touched)[:5])}

Grouping rationale: {group.rationale}

Generate a single conventional commit message that summarizes these changes. 
The message should:
1. Follow the format: type(scope): subject
2. Be concise but descriptive
3. Focus on the overall change, not individual commits
4. Be under 50 characters for the subject line

Return ONLY the commit message, nothing else."""
        
        return prompt
    
    def _validate_message(self, message: str) -> bool:
        """Validate that the generated message follows conventional commit format."""
        if not message:
            return False
            
        # Basic validation - should start with a type
        valid_types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'perf', 'ci', 'build']
        
        # Check if message starts with valid type
        for commit_type in valid_types:
            if message.startswith(f"{commit_type}:") or message.startswith(f"{commit_type}("):
                return True
                
        return False