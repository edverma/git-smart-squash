"""Token counting and management utilities for AI operations."""

import json
from typing import List, Dict, Any, Tuple, Optional
from ..core.models import Commit


class TokenManager:
    """Manages token counting and batch processing for AI operations."""
    
    def __init__(self, max_response_tokens: int = 12000, token_headroom: int = 1000):
        self.max_response_tokens = max_response_tokens
        self.token_headroom = token_headroom
        self._tokenizer = None
        
    def _get_tokenizer(self):
        """Get tiktoken tokenizer (lazy loaded)."""
        if self._tokenizer is None:
            try:
                import tiktoken
                # Use cl100k_base which works well for most models including Mistral/Llama
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                raise ImportError("tiktoken is required for token counting. Install with: pip install tiktoken")
        return self._tokenizer
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        tokenizer = self._get_tokenizer()
        return len(tokenizer.encode(text))
    
    def estimate_response_tokens(self, num_commits: int) -> int:
        """Estimate tokens needed for AI response based on number of commits."""
        # Base JSON structure: ~100 tokens
        base_tokens = 100
        
        # Per commit: ~15-30 tokens for JSON structure + commit indices
        # {"id": "group_1", "commit_indices": [0,1,2], "rationale": "...", "suggested_type": "feat", "suggested_scope": "...", "suggested_message": "..."}
        tokens_per_commit = 25
        
        # Add some buffer for rationale and suggested messages
        rationale_buffer = num_commits * 10  # ~10 tokens per rationale
        
        return base_tokens + (num_commits * tokens_per_commit) + rationale_buffer
    
    def calculate_num_predict(self, prompt_tokens: int, num_commits: int) -> int:
        """Calculate optimal num_predict value with headroom."""
        estimated_response = self.estimate_response_tokens(num_commits)
        target_tokens = estimated_response + self.token_headroom
        
        # Cap at maximum
        return min(target_tokens, self.max_response_tokens)
    
    def should_use_batching(self, prompt_tokens: int, num_commits: int) -> bool:
        """Determine if batching is needed based on token counts."""
        estimated_response = self.estimate_response_tokens(num_commits)
        total_needed = prompt_tokens + estimated_response + self.token_headroom
        
        # Use batching if:
        # 1. The response alone would exceed our max response tokens (12k)
        # 2. The total context (prompt + response + headroom) would exceed 32k
        # 3. We have more than 40 commits (empirical threshold)
        return (estimated_response > self.max_response_tokens or 
                total_needed > 32000 or 
                num_commits > 40)
    
    def create_batches(self, commits: List[Commit], target_batch_size: int = 20) -> List[List[Commit]]:
        """Split commits into smaller batches for processing."""
        batches = []
        for i in range(0, len(commits), target_batch_size):
            batch = commits[i:i + target_batch_size]
            batches.append(batch)
        return batches
    
    def estimate_prompt_tokens(self, commit_data: Dict[str, Any]) -> int:
        """Estimate tokens in the grouping prompt without building the full prompt."""
        # Base prompt structure: ~300 tokens
        base_tokens = 300
        
        # Per commit estimation:
        # - Hash, message, author, time, files, changes: ~50 tokens
        # - Diff (truncated to 500 chars): ~125 tokens
        # - Formatting overhead: ~25 tokens
        tokens_per_commit = 200
        
        num_commits = commit_data.get('total_commits', 0)
        return base_tokens + (num_commits * tokens_per_commit)


def optimize_commit_data_for_tokens(commits: List[Commit]) -> Dict[str, Any]:
    """Create optimized commit data that reduces token usage."""
    commit_data = []
    
    for i, commit in enumerate(commits):
        # More aggressive truncation for large commit sets
        diff_limit = 300 if len(commits) > 30 else 500
        truncated_diff = commit.diff[:diff_limit] if len(commit.diff) > diff_limit else commit.diff
        
        # Limit file list to most important files
        files_limit = 3 if len(commits) > 30 else 5
        files = commit.files[:files_limit]
        if len(commit.files) > files_limit:
            files.append(f"... and {len(commit.files) - files_limit} more")
        
        commit_info = {
            "index": i,
            "hash": commit.short_hash,
            "message": commit.message[:100] if len(commit.message) > 100 else commit.message,  # Truncate long messages
            "author": commit.author,
            "timestamp": commit.timestamp.isoformat(),
            "files": files,
            "insertions": commit.insertions,
            "deletions": commit.deletions,
            "diff": truncated_diff
        }
        commit_data.append(commit_info)
    
    return {
        "commits": commit_data,
        "total_commits": len(commits)
    }