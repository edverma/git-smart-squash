"""Core data models for Git Smart Squash."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set
from .constants import (
    DEFAULT_TIME_WINDOW,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_COMMIT_TYPES,
    MAX_SUBJECT_LENGTH
)


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
    time_window: int = DEFAULT_TIME_WINDOW
    min_file_overlap: int = 1  # minimum shared files
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD


@dataclass
class CommitFormatConfig:
    """Configuration for commit message formatting."""
    types: List[str] = None
    scope_required: bool = False
    max_subject_length: int = MAX_SUBJECT_LENGTH
    body_required: bool = False
    
    def __post_init__(self):
        if self.types is None:
            self.types = DEFAULT_COMMIT_TYPES


@dataclass
class AIConfig:
    """Configuration for AI providers."""
    provider: str = "local"  # or openai, anthropic
    model: str = "devstral"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None  # Custom base URL for OpenAI-compatible APIs


@dataclass
class OutputConfig:
    """Configuration for output behavior."""
    dry_run_default: bool = True
    backup_branch: bool = True
    force_push_protection: bool = True


@dataclass
class Config:
    """Main configuration object."""
    grouping: GroupingConfig = field(default_factory=GroupingConfig)
    commit_format: CommitFormatConfig = field(default_factory=CommitFormatConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    output: OutputConfig = field(default_factory=OutputConfig)