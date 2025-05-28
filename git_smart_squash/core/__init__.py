"""Core functionality for git-smart-squash."""

# Don't import models here to avoid circular imports
# Import them directly where needed instead

__all__ = [
    'models',
    'git_parser',
    'commit_analyzer'
]