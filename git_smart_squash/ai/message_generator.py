"""Main AI message generator that coordinates different providers."""

from typing import Optional
from ..models import CommitGroup, AIConfig
from ..utils.message import validate_and_format_message
from .providers.openai import OpenAIProvider
from .providers.anthropic import AnthropicProvider
from .providers.local import LocalProvider


class MessageGenerator:
    """Generates commit messages using AI providers."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.provider = self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the appropriate AI provider based on config."""
        if self.config.provider.lower() == "openai":
            return OpenAIProvider(self.config)
        elif self.config.provider.lower() == "anthropic":
            return AnthropicProvider(self.config)
        elif self.config.provider.lower() == "local":
            return LocalProvider(self.config)
        else:
            raise ValueError(f"Unsupported AI provider: {self.config.provider}")
    
    def generate_message(self, group: CommitGroup) -> str:
        """Generate a commit message for a group of commits."""
        try:
            # Generate message using the provider
            message = self.provider.generate_commit_message(group)
            
            if message:
                # Validate and format the message
                return validate_and_format_message(message)
            else:
                # Provider returned None, use fallback
                return group.suggested_message
            
        except Exception as e:
            # Fallback to the basic suggested message
            return group.suggested_message
    
    def _build_context(self, group: CommitGroup) -> dict:
        """Build context dictionary for AI generation."""
        # Aggregate commit information
        messages = [commit.message for commit in group.commits]
        all_diffs = "\n".join([commit.diff for commit in group.commits])
        
        # Limit diff size to avoid token limits
        max_diff_length = 8000  # Reasonable limit for most AI providers
        if len(all_diffs) > max_diff_length:
            all_diffs = all_diffs[:max_diff_length] + "\n... (truncated)"
        
        # Extract file information
        file_changes = []
        for commit in group.commits:
            for file_path in commit.files:
                file_changes.append({
                    'path': file_path,
                    'commit_hash': commit.short_hash,
                    'commit_message': commit.message
                })
        
        context = {
            'commit_count': len(group.commits),
            'commit_type': group.commit_type,
            'scope': group.scope,
            'original_messages': messages,
            'files_touched': list(group.files_touched),
            'file_changes': file_changes,
            'total_insertions': group.total_insertions,
            'total_deletions': group.total_deletions,
            'rationale': group.rationale,
            'diffs': all_diffs,
            'time_span': self._calculate_time_span(group),
            'suggested_message': group.suggested_message
        }
        
        return context
    
    def _calculate_time_span(self, group: CommitGroup) -> str:
        """Calculate the time span of commits in the group."""
        if len(group.commits) <= 1:
            return "single commit"
        
        sorted_commits = sorted(group.commits, key=lambda c: c.timestamp)
        time_span = sorted_commits[-1].timestamp - sorted_commits[0].timestamp
        
        total_minutes = int(time_span.total_seconds() / 60)
        
        if total_minutes < 60:
            return f"{total_minutes} minutes"
        elif total_minutes < 1440:  # Less than 24 hours
            hours = total_minutes / 60
            return f"{hours:.1f} hours"
        else:
            days = total_minutes / 1440
            return f"{days:.1f} days"
    


class TemplateMessageGenerator:
    """Fallback message generator using templates when AI is not available."""
    
    def __init__(self):
        self.templates = {
            'feat': [
                "Add {feature}",
                "Implement {feature}",
                "Create {feature}"
            ],
            'fix': [
                "Fix {issue}",
                "Resolve {issue}",
                "Correct {issue}"
            ],
            'refactor': [
                "Refactor {component}",
                "Improve {component}",
                "Update {component}"
            ],
            'docs': [
                "Update documentation",
                "Add documentation for {component}",
                "Improve docs"
            ],
            'test': [
                "Add tests for {component}",
                "Update test suite",
                "Improve test coverage"
            ],
            'chore': [
                "Update {component}",
                "Maintenance updates",
                "Project updates"
            ],
            'style': [
                "Format code",
                "Style improvements",
                "Code formatting"
            ]
        }
    
    def generate_message(self, group: CommitGroup) -> str:
        """Generate a template-based message."""
        commit_type = group.commit_type
        templates = self.templates.get(commit_type, self.templates['chore'])
        
        # Choose template based on context
        template = templates[0]  # Default to first template
        
        # Try to extract component/feature name from files
        component = self._extract_component_name(group)
        
        if '{feature}' in template or '{component}' in template or '{issue}' in template:
            replacement = component if component else "functionality"
            message = template.format(
                feature=replacement,
                component=replacement,
                issue=replacement
            )
        else:
            message = template
        
        # Add scope if available
        if group.scope:
            return f"{commit_type}({group.scope}): {message.lower()}"
        else:
            return f"{commit_type}: {message.lower()}"
    
    def _extract_component_name(self, group: CommitGroup) -> str:
        """Extract a component name from the group's files."""
        files = list(group.files_touched)
        
        if not files:
            return ""
        
        # If single file, use filename without extension
        if len(files) == 1:
            filename = files[0].split('/')[-1]
            return filename.split('.')[0]
        
        # Multiple files - try to find common component
        # Look for common directory names
        common_dirs = set()
        for file_path in files:
            parts = file_path.split('/')[:-1]  # Exclude filename
            common_dirs.update(parts)
        
        # Filter out common directory names that aren't meaningful
        exclude_dirs = {'src', 'lib', 'app', 'components', 'utils', 'test', 'tests'}
        meaningful_dirs = [d for d in common_dirs if d not in exclude_dirs and len(d) > 2]
        
        if meaningful_dirs:
            return meaningful_dirs[0]
        
        return "multiple files"