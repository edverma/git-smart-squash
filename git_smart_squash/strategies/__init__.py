"""Strategy pattern implementations for applying commits."""

from .base import CommitApplicationStrategy
from .git_native_strategy import GitNativeStrategy
from .legacy_patch_strategy import LegacyPatchStrategy
from .legacy_adapter import LegacyToStrategyAdapter

__all__ = [
    "CommitApplicationStrategy",
    "GitNativeStrategy",
    "LegacyPatchStrategy",
    "LegacyToStrategyAdapter",
]
