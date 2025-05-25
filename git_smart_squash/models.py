"""Core data models for Git Smart Squash."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set


@dataclass
class Commit:
    """Represents a single git commit with all relevant metadata."""
    hash: str
    short_hash: str
    author: str
    email: str
    timestamp: datetime
    message: str
    files: List[str]
    insertions: int
    deletions: int
    diff: str
    parent_hash: str


@dataclass
class CommitGroup:
    """Represents a group of related commits that should be squashed together."""
    id: str
    commits: List[Commit]
    rationale: str  # Why these were grouped
    suggested_message: str
    commit_type: str  # feat, fix, etc.
    scope: Optional[str]
    files_touched: Set[str]
    total_insertions: int
    total_deletions: int


@dataclass
class RebaseOperation:
    """Represents a single operation in a git rebase interactive sequence."""
    action: str  # pick, squash, fixup, drop
    commit: Commit
    target_group: Optional[CommitGroup]


@dataclass
class GroupingConfig:
    """Configuration for commit grouping strategies."""
    time_window: int = 1800  # seconds
    min_file_overlap: int = 1  # minimum shared files
    similarity_threshold: float = 0.7  # for semantic matching


@dataclass
class CommitFormatConfig:
    """Configuration for commit message formatting."""
    types: List[str] = None
    scope_required: bool = False
    max_subject_length: int = 50
    body_required: bool = False
    
    def __post_init__(self):
        if self.types is None:
            self.types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']


@dataclass
class AIConfig:
    """Configuration for AI providers."""
    provider: str = "openai"  # or anthropic, local
    model: str = "gpt-4"
    api_key_env: str = "OPENAI_API_KEY"


@dataclass
class OutputConfig:
    """Configuration for output behavior."""
    dry_run_default: bool = True
    backup_branch: bool = True
    force_push_protection: bool = True


@dataclass
class Config:
    """Main configuration object."""
    grouping: GroupingConfig
    commit_format: CommitFormatConfig
    ai: AIConfig
    output: OutputConfig
    
    def __init__(self):
        self.grouping = GroupingConfig()
        self.commit_format = CommitFormatConfig()
        self.ai = AIConfig()
        self.output = OutputConfig()