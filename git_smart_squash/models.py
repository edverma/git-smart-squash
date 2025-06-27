"""Data models for git-smart-squash."""

from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from enum import Enum


class ChangeType(Enum):
    """Types of changes in a hunk."""

    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    IMPORT = "import"
    EXPORT = "export"


class ConflictType(Enum):
    """Types of conflicts that can occur during application."""

    MERGE_CONFLICT = "merge_conflict"
    FILE_DELETED = "file_deleted"
    BINARY_CONFLICT = "binary_conflict"
    LINE_NUMBER_SHIFT = "line_number_shift"


@dataclass
class Hunk:
    """Represents a single change hunk in a file."""

    id: str  # Format: "file_path:start_line-end_line"
    file_path: str
    start_line: int
    end_line: int
    content: str  # The actual diff content
    context: str = ""  # Surrounding code context
    dependencies: Set[str] = field(
        default_factory=set
    )  # Other hunk IDs this depends on
    dependents: Set[str] = field(default_factory=set)  # Hunk IDs that depend on this
    change_type: ChangeType = ChangeType.MODIFICATION
    old_content: Optional[str] = None  # Content being replaced
    new_content: Optional[str] = None  # New content
    is_binary: bool = False  # For binary file changes


@dataclass
class CommitGroup:
    """Group of related changes that should be committed together."""

    id: str
    message: str
    hunks: List[Hunk]
    rationale: str = ""
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # Other commit group IDs

    @property
    def file_paths(self) -> Set[str]:
        """Get all unique file paths in this commit group."""
        return {hunk.file_path for hunk in self.hunks}


@dataclass
class ConflictInfo:
    """Information about a conflict during commit application."""

    file_path: str
    conflict_type: ConflictType
    our_changes: Optional[str] = None
    their_changes: Optional[str] = None
    base_content: Optional[str] = None
    hunk: Optional[Hunk] = None
    error_message: Optional[str] = None


class ResultStatus(Enum):
    """Status of an operation result."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    CONFLICT = "conflict"


@dataclass
class Result:
    """Result of an operation."""

    status: ResultStatus
    message: str = ""
    data: Optional[Any] = None
    conflicts: List[ConflictInfo] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.status == ResultStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        return self.status == ResultStatus.FAILURE

    @property
    def has_conflicts(self) -> bool:
        return self.status == ResultStatus.CONFLICT or len(self.conflicts) > 0

    @classmethod
    def success(cls, data: Any = None, message: str = "") -> "Result":
        return cls(ResultStatus.SUCCESS, message, data)

    @classmethod
    def failure(cls, message: str, data: Any = None) -> "Result":
        return cls(ResultStatus.FAILURE, message, data)

    @classmethod
    def conflict(cls, conflicts: List[ConflictInfo], message: str = "") -> "Result":
        return cls(ResultStatus.CONFLICT, message, conflicts=conflicts)


@dataclass
class Resolution:
    """Resolution for a conflict."""

    action: str  # "use_ours", "use_theirs", "manual", "skip"
    content: Optional[str] = None  # For manual resolution
    reason: str = ""
