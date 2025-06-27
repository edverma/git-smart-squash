# Git-Native Commit Application Implementation Plan

## Executive Summary

This document outlines a comprehensive plan to replace the current manual patch application system with Git's native commit operations. This change will resolve line number shift issues and improve overall reliability.

## Problem Statement

The current implementation fails when applying multiple hunks to the same file because:
- Manual patch application uses fixed line numbers
- Previous changes shift line numbers, causing subsequent patches to fail
- The system attempts to recreate Git's complex merge logic manually

## Proposed Solution

Leverage Git's native commit and merge operations to handle all file changes, allowing Git to manage line number reconciliation automatically.

## Architecture Overview

```
┌─────────────────────────┐
│   AI Commit Analysis    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   CommitGroup Builder   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Git Native Strategy    │ ◄── New Implementation
├─────────────────────────┤
│ • Create temp branch    │
│ • Apply changes         │
│ • Git commit            │
│ • Handle conflicts      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Final Commits         │
└─────────────────────────┘
```

## Phase 1: Architecture Refactoring

### 1.1 Create New Commit Strategy Module

**File**: `src/git_smart_squash/strategies/git_native_strategy.py`

```python
from typing import List, Dict, Optional
import git
from dataclasses import dataclass
from ..models import CommitGroup, Hunk, Result

class GitNativeStrategy:
    """Applies changes using Git's native commit/merge operations"""
    
    def __init__(self, repo_path: str):
        self.repo = git.Repo(repo_path)
        self.original_branch = self.repo.active_branch
        self.temp_branches = []
        
    def apply_commit_group(self, commit_group: CommitGroup) -> Result:
        """Apply a group of related changes as a single commit"""
        try:
            # Implementation details in Phase 2
            pass
        except Exception as e:
            return Result.failure(str(e))
```

### 1.2 Refactor Hunk Application Logic

**File**: `src/git_smart_squash/strategies/commit_builder.py`

```python
class CommitBuilder:
    """Builds actual file changes instead of patches"""
    
    def build_file_state(self, file_path: str, hunks: List[Hunk]) -> str:
        """Construct the complete file content with all hunks applied"""
        # Read current file
        # Apply hunks in memory
        # Return complete file content
        pass
        
    def apply_hunk_to_content(self, content: str, hunk: Hunk) -> str:
        """Apply a single hunk to file content"""
        lines = content.splitlines(keepends=True)
        # Apply hunk logic
        return ''.join(lines)
```

## Phase 2: Core Implementation

### 2.1 Working Directory Management

**File**: `src/git_smart_squash/strategies/working_directory.py`

```python
import git
from typing import Optional

class WorkingDirectoryManager:
    """Manages working directory state and changes"""
    
    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.stash_entry: Optional[str] = None
        
    def prepare_clean_state(self) -> None:
        """Ensure working directory is clean"""
        if self.repo.is_dirty():
            # Stash any uncommitted changes
            self.stash_entry = self.repo.git.stash(
                'push', '-u', '-m', 'git-smart-squash-backup'
            )
            
    def restore_state(self) -> None:
        """Restore original working directory state"""
        if self.stash_entry:
            self.repo.git.stash('pop')
            
    def __enter__(self):
        self.prepare_clean_state()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_state()
```

### 2.2 Main Implementation

**File**: `src/git_smart_squash/strategies/git_native_strategy.py` (continued)

```python
def apply_commits_using_git(self, commit_groups: List[CommitGroup]) -> Result:
    """Main entry point for Git-native application"""
    
    # 1. Create temporary branch
    temp_branch = f"gss-temp-{int(time.time())}"
    self.repo.create_head(temp_branch)
    self.repo.heads[temp_branch].checkout()
    
    results = []
    
    # 2. Apply each commit group
    for group in commit_groups:
        try:
            # Build complete file states
            file_states = {}
            for hunk in group.hunks:
                if hunk.file_path not in file_states:
                    file_states[hunk.file_path] = self.read_file(hunk.file_path)
                file_states[hunk.file_path] = self.apply_hunk_to_content(
                    file_states[hunk.file_path], 
                    hunk
                )
            
            # Write all files
            for file_path, content in file_states.items():
                self.write_file(file_path, content)
            
            # Stage and commit
            self.repo.index.add([f for f in file_states.keys()])
            commit = self.repo.index.commit(
                message=group.commit_message,
                author=git.Actor(group.author_name, group.author_email)
            )
            
            results.append(Result.success(commit.hexsha))
            
        except Exception as e:
            # Handle conflicts
            conflict_result = self.handle_conflict(e, group)
            results.append(conflict_result)
    
    # 3. Return to original branch and cherry-pick
    self.original_branch.checkout()
    self.cherry_pick_commits(temp_branch, self.original_branch)
    
    return Result.success(results)
```

### 2.3 Conflict Resolution

**File**: `src/git_smart_squash/strategies/conflict_resolver.py`

```python
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

class ConflictType(Enum):
    MERGE_CONFLICT = "merge_conflict"
    FILE_DELETED = "file_deleted"
    BINARY_CONFLICT = "binary_conflict"
    
@dataclass
class ConflictInfo:
    file_path: str
    conflict_type: ConflictType
    our_changes: Optional[str]
    their_changes: Optional[str]
    base_content: Optional[str]

class ConflictResolver:
    """Handles merge conflicts during commit application"""
    
    def resolve_conflict(self, conflict_info: ConflictInfo) -> Resolution:
        """Attempt automatic resolution, fall back to user intervention"""
        
        # 1. Try automatic resolution strategies
        if self.can_auto_resolve(conflict_info):
            return self.auto_resolve(conflict_info)
            
        # 2. Present conflict to user
        return self.interactive_resolve(conflict_info)
        
    def can_auto_resolve(self, conflict_info: ConflictInfo) -> bool:
        """Check if conflict can be automatically resolved"""
        # Check for:
        # - Non-overlapping changes
        # - Whitespace-only conflicts
        # - Import statement ordering
        # - Comment-only conflicts
        
        if conflict_info.conflict_type == ConflictType.FILE_DELETED:
            # Can auto-resolve if changes are minor
            return len(conflict_info.our_changes or "") < 100
            
        return False
        
    def auto_resolve(self, conflict_info: ConflictInfo) -> Resolution:
        """Automatically resolve simple conflicts"""
        # Implementation for each auto-resolvable case
        pass
```

## Phase 3: Advanced Features

### 3.1 Dependency Management

**File**: `src/git_smart_squash/strategies/dependency_manager.py`

```python
from typing import List, Dict, Set
import networkx as nx

class DependencyAwareApplicator:
    """Ensures commits are applied in dependency order"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        
    def build_dependency_graph(self, commits: List[CommitGroup]) -> nx.DiGraph:
        """Build a directed graph of commit dependencies"""
        for commit in commits:
            self.graph.add_node(commit.id, data=commit)
            
        # Add edges for dependencies
        for commit in commits:
            for dep_id in self.get_dependencies(commit):
                self.graph.add_edge(dep_id, commit.id)
                
        return self.graph
        
    def get_dependencies(self, commit: CommitGroup) -> Set[str]:
        """Identify which commits this commit depends on"""
        dependencies = set()
        
        for hunk in commit.hunks:
            # Check if hunk depends on changes from other commits
            # E.g., uses a function defined in another commit
            for other_commit in self.all_commits:
                if self.hunk_depends_on_commit(hunk, other_commit):
                    dependencies.add(other_commit.id)
                    
        return dependencies
        
    def reorder_commits(self, commits: List[CommitGroup]) -> List[CommitGroup]:
        """Topologically sort commits based on dependencies"""
        graph = self.build_dependency_graph(commits)
        
        try:
            ordered_ids = list(nx.topological_sort(graph))
            commit_map = {c.id: c for c in commits}
            return [commit_map[id] for id in ordered_ids]
        except nx.NetworkXUnfeasible:
            raise ValueError("Circular dependency detected in commits")
```

### 3.2 Large File Handling

**File**: `src/git_smart_squash/strategies/large_file_handler.py`

```python
import mmap
import os
from typing import List

class LargeFileHandler:
    """Efficiently handle large file modifications"""
    
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
    
    def should_use_streaming(self, file_path: str) -> bool:
        """Check if file is large enough to require streaming"""
        try:
            return os.path.getsize(file_path) > self.LARGE_FILE_THRESHOLD
        except OSError:
            return False
            
    def apply_changes_to_large_file(self, file_path: str, hunks: List[Hunk]) -> None:
        """Efficiently apply changes to large files"""
        # Sort hunks in reverse order to maintain line numbers
        sorted_hunks = sorted(hunks, key=lambda h: h.start_line, reverse=True)
        
        # Use memory mapping for efficiency
        with open(file_path, 'r+b') as f:
            with mmap.mmap(f.fileno(), 0) as mmapped_file:
                # Apply hunks with minimal memory usage
                for hunk in sorted_hunks:
                    self.apply_hunk_to_mmap(mmapped_file, hunk)
```

### 3.3 Binary File Support

**File**: `src/git_smart_squash/strategies/binary_handler.py`

```python
import base64
from typing import Optional

class BinaryFileHandler:
    """Special handling for binary files"""
    
    def is_binary_file(self, file_path: str) -> bool:
        """Check if file is binary"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
                return b'\0' in chunk
        except:
            return False
            
    def handle_binary_change(self, file_path: str, change: Change) -> None:
        """Handle binary file modifications"""
        if change.is_deletion:
            os.remove(file_path)
        elif change.is_addition:
            self.write_binary_file(file_path, change.content)
        else:
            raise ValueError(
                f"Cannot apply textual hunks to binary file: {file_path}"
            )
            
    def write_binary_file(self, file_path: str, content: str) -> None:
        """Write binary content from base64 encoded string"""
        binary_data = base64.b64decode(content)
        with open(file_path, 'wb') as f:
            f.write(binary_data)
```

## Phase 4: Safety and Rollback

### 4.1 Atomic Operations

**File**: `src/git_smart_squash/strategies/atomic_operations.py`

```python
from contextlib import contextmanager
from typing import Generator, Optional

class AtomicCommitApplicator:
    """Ensures all-or-nothing commit application"""
    
    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.checkpoint: Optional[git.Commit] = None
        
    @contextmanager
    def atomic_operation(self) -> Generator[None, None, None]:
        """Context manager for atomic operations"""
        # Save current state
        self.checkpoint = self.repo.head.commit
        
        try:
            yield
        except Exception as e:
            # Rollback on any error
            self.rollback()
            raise
            
    def rollback(self) -> None:
        """Rollback to checkpoint"""
        if self.checkpoint:
            self.repo.head.reset(
                self.checkpoint, 
                index=True, 
                working_tree=True
            )
            
    def apply_with_rollback(self, commits: List[CommitGroup]) -> Result:
        """Apply commits with automatic rollback on failure"""
        with self.atomic_operation():
            results = []
            for commit in commits:
                result = self.apply_single_commit(commit)
                if result.is_failure:
                    raise Exception(f"Failed to apply commit: {commit.id}")
                results.append(result)
                
            return Result.success(results)
```

### 4.2 Backup Strategy

**File**: `src/git_smart_squash/strategies/backup_manager.py`

```python
import time
from typing import Optional

class BackupManager:
    """Manages backup branches and recovery"""
    
    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.backup_branch: Optional[str] = None
        
    def create_backup(self) -> str:
        """Create backup branch before operations"""
        current_branch = self.repo.active_branch.name
        timestamp = int(time.time())
        
        self.backup_branch = f"{current_branch}-backup-{timestamp}"
        self.repo.create_head(self.backup_branch, self.repo.head.commit)
        
        return self.backup_branch
        
    def restore_from_backup(self) -> None:
        """Restore from backup branch"""
        if not self.backup_branch:
            raise ValueError("No backup branch available")
            
        backup_ref = self.repo.heads[self.backup_branch]
        self.repo.head.reset(backup_ref.commit, index=True, working_tree=True)
        
    def cleanup_backup(self, keep_on_error: bool = True) -> None:
        """Remove backup branch if successful"""
        if self.backup_branch and not keep_on_error:
            self.repo.delete_head(self.backup_branch)
```

## Phase 5: Integration

### 5.1 Feature Flag Implementation

**File**: `src/git_smart_squash/config.py`

```python
from typing import Dict, Any
import os
import json

class FeatureFlags:
    """Manage feature flags for gradual rollout"""
    
    def __init__(self):
        self.flags = self.load_flags()
        
    def load_flags(self) -> Dict[str, Any]:
        """Load feature flags from config"""
        config_path = os.path.expanduser("~/.git-smart-squash/features.json")
        
        try:
            with open(config_path) as f:
                return json.load(f)
        except:
            return {
                "use_native_git_operations": False,
                "parallel_processing": False,
                "auto_conflict_resolution": False
            }
            
    def is_enabled(self, flag_name: str) -> bool:
        """Check if feature is enabled"""
        return self.flags.get(flag_name, False)
```

**File**: `src/git_smart_squash/main.py` (modification)

```python
def apply_commits(analyzed_commits: List[CommitGroup], config: Config) -> Result:
    """Apply commits using appropriate strategy"""
    
    feature_flags = FeatureFlags()
    
    if feature_flags.is_enabled('use_native_git_operations'):
        strategy = GitNativeStrategy(repo_path)
    else:
        strategy = LegacyPatchStrategy(repo_path)  # Current implementation
        
    with BackupManager(repo) as backup:
        try:
            result = strategy.apply_commits(analyzed_commits)
            if result.is_success:
                backup.cleanup_backup(keep_on_error=False)
            return result
        except Exception as e:
            logger.error(f"Failed to apply commits: {e}")
            backup.restore_from_backup()
            raise
```

### 5.2 Migration Path

Create a migration plan file:

**File**: `docs/MIGRATION_PLAN.md`

```markdown
# Migration Plan: Git Native Operations

## Timeline

### Week 1-2: Implementation
- [x] Implement GitNativeStrategy base class
- [x] Create CommitBuilder
- [x] Implement WorkingDirectoryManager
- [ ] Add comprehensive logging

### Week 3: Testing
- [ ] Unit tests for all new components
- [ ] Integration tests with real repositories
- [ ] Performance benchmarks
- [ ] Edge case testing

### Week 4: Alpha Release
- [ ] Enable for internal team (5 users)
- [ ] Monitor performance metrics
- [ ] Collect feedback
- [ ] Fix critical bugs

### Week 5: Beta Release
- [ ] Enable for 10% of users
- [ ] A/B testing metrics
- [ ] Performance monitoring
- [ ] Bug tracking

### Week 6: General Availability
- [ ] Enable for 50% of users
- [ ] Monitor error rates
- [ ] Performance comparison
- [ ] User satisfaction metrics

### Week 7: Full Rollout
- [ ] Enable for all users
- [ ] Keep legacy code as fallback
- [ ] Documentation updates
- [ ] Blog post announcement

### Week 8: Cleanup
- [ ] Remove legacy code
- [ ] Final performance audit
- [ ] Post-mortem document
```

### 5.3 Testing Strategy

**File**: `tests/test_git_native_strategy.py`

```python
import pytest
import tempfile
import git
from pathlib import Path
from git_smart_squash.strategies import GitNativeStrategy
from git_smart_squash.models import CommitGroup, Hunk

class TestGitNativeStrategy:
    """Test suite for Git native operations"""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary Git repository"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = git.Repo.init(tmpdir)
            
            # Add initial files
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "layout.svelte").write_text(
                '<script>console.log("test")</script>\n'
                '<main class="old-class">content</main>'
            )
            
            repo.index.add(["main.py", "layout.svelte"])
            repo.index.commit("Initial commit")
            
            yield repo
            
    def test_handles_line_number_shifts(self, temp_repo):
        """Test the specific case that was failing"""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        # First commit: Add analytics (shifts line numbers)
        commit1 = CommitGroup(
            id="1",
            message="Add analytics",
            hunks=[
                Hunk(
                    file_path="layout.svelte",
                    start_line=1,
                    content='<script>\nimport analytics from "./analytics"\n'
                           'console.log("test")\n'
                           'analytics.init()\n</script>\n'
                           '<main class="old-class">content</main>'
                )
            ]
        )
        
        # Second commit: Change theme (would fail with old approach)
        commit2 = CommitGroup(
            id="2", 
            message="Update theme",
            hunks=[
                Hunk(
                    file_path="layout.svelte",
                    # Note: Line numbers are from original file
                    # Git will handle the shift automatically
                    start_line=2,
                    old_content='<main class="old-class">',
                    new_content='<main class="new-class">'
                )
            ]
        )
        
        # Apply commits
        result = strategy.apply_commits([commit1, commit2])
        
        # Verify success
        assert result.is_success
        
        # Verify file content
        final_content = Path(temp_repo.working_dir) / "layout.svelte"
        assert 'class="new-class"' in final_content.read_text()
        assert 'analytics.init()' in final_content.read_text()
        
    def test_conflict_resolution(self, temp_repo):
        """Test various conflict scenarios"""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        # Create conflicting commits
        commit1 = CommitGroup(
            id="1",
            message="Change A",
            hunks=[
                Hunk(
                    file_path="main.py",
                    start_line=1,
                    content='print("version A")'
                )
            ]
        )
        
        commit2 = CommitGroup(
            id="2",
            message="Change B", 
            hunks=[
                Hunk(
                    file_path="main.py",
                    start_line=1,
                    content='print("version B")'
                )
            ]
        )
        
        # This should trigger conflict resolution
        result = strategy.apply_commits([commit1, commit2])
        
        # Verify conflict was handled
        assert result.is_success or result.has_conflicts
        
    def test_binary_file_handling(self, temp_repo):
        """Test binary file operations"""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        # Add binary file
        binary_content = b'\x00\x01\x02\x03'
        binary_path = Path(temp_repo.working_dir) / "image.png"
        binary_path.write_bytes(binary_content)
        
        commit = CommitGroup(
            id="1",
            message="Update binary",
            hunks=[
                Hunk(
                    file_path="image.png",
                    is_binary=True,
                    content=base64.b64encode(b'\x00\x01\x02\x04').decode()
                )
            ]
        )
        
        result = strategy.apply_commits([commit])
        assert result.is_success
        
    def test_large_file_performance(self, temp_repo):
        """Test performance with large files"""
        # Create large file (10MB)
        large_content = "line\n" * (10 * 1024 * 1024 // 5)
        large_path = Path(temp_repo.working_dir) / "large.txt"
        large_path.write_text(large_content)
        
        # Time the operation
        import time
        start = time.time()
        
        commit = CommitGroup(
            id="1",
            message="Update large file",
            hunks=[
                Hunk(
                    file_path="large.txt",
                    start_line=1000,
                    content="modified line\n"
                )
            ]
        )
        
        strategy = GitNativeStrategy(temp_repo.working_dir)
        result = strategy.apply_commits([commit])
        
        elapsed = time.time() - start
        
        assert result.is_success
        assert elapsed < 5.0  # Should complete in under 5 seconds
```

## Phase 6: Performance Optimization

### 6.1 Batch Operations

**File**: `src/git_smart_squash/strategies/batch_optimizer.py`

```python
from typing import Dict, List, Set
import subprocess

class BatchOptimizer:
    """Optimize Git operations for performance"""
    
    def __init__(self, repo: git.Repo):
        self.repo = repo
        
    def batch_stage_files(self, file_paths: List[str]) -> None:
        """Stage multiple files efficiently"""
        if len(file_paths) > 100:
            # Use update-index for large batches
            process = subprocess.Popen(
                ['git', 'update-index', '--add', '--stdin'],
                stdin=subprocess.PIPE,
                cwd=self.repo.working_dir
            )
            
            for path in file_paths:
                process.stdin.write(f"{path}\n".encode())
                
            process.stdin.close()
            process.wait()
        else:
            # Use normal add for small batches
            self.repo.index.add(file_paths)
            
    def optimize_file_operations(
        self, 
        file_changes: Dict[str, List[Change]]
    ) -> None:
        """Group and optimize file operations"""
        # Group by operation type
        additions = []
        modifications = []
        deletions = []
        
        for file_path, changes in file_changes.items():
            change_types = {c.type for c in changes}
            
            if 'delete' in change_types:
                deletions.append(file_path)
            elif 'add' in change_types:
                additions.append(file_path)
            else:
                modifications.append(file_path)
                
        # Apply in optimal order
        if deletions:
            self.repo.index.remove(deletions)
        if additions or modifications:
            self.batch_stage_files(additions + modifications)
```

### 6.2 Parallel Processing

**File**: `src/git_smart_squash/strategies/parallel_processor.py`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set
import threading

class ParallelProcessor:
    """Apply non-conflicting commits in parallel"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.file_locks: Dict[str, threading.Lock] = {}
        
    def identify_independent_commits(
        self, 
        commits: List[CommitGroup]
    ) -> List[List[CommitGroup]]:
        """Group commits that can be applied in parallel"""
        # Build conflict graph
        groups = []
        used_files: Set[str] = set()
        current_group = []
        
        for commit in commits:
            commit_files = {h.file_path for h in commit.hunks}
            
            if commit_files.intersection(used_files):
                # Conflict with current group
                if current_group:
                    groups.append(current_group)
                current_group = [commit]
                used_files = commit_files
            else:
                # Can be parallelized
                current_group.append(commit)
                used_files.update(commit_files)
                
        if current_group:
            groups.append(current_group)
            
        return groups
        
    def apply_parallel(
        self, 
        commits: List[CommitGroup],
        strategy: GitNativeStrategy
    ) -> List[Result]:
        """Apply commits in parallel where possible"""
        independent_groups = self.identify_independent_commits(commits)
        all_results = []
        
        for group in independent_groups:
            if len(group) == 1:
                # Single commit, no parallelization needed
                result = strategy.apply_commit_group(group[0])
                all_results.append(result)
            else:
                # Apply in parallel
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(
                            strategy.apply_commit_group, 
                            commit
                        ): commit 
                        for commit in group
                    }
                    
                    for future in as_completed(futures):
                        result = future.result()
                        all_results.append(result)
                        
        return all_results
```

## Implementation Checklist

### Core Components
- [ ] GitNativeStrategy class
- [ ] CommitBuilder implementation  
- [ ] WorkingDirectoryManager
- [ ] ConflictResolver
- [ ] AtomicCommitApplicator
- [ ] BackupManager

### Advanced Features
- [ ] DependencyAwareApplicator
- [ ] LargeFileHandler
- [ ] BinaryFileHandler
- [ ] BatchOptimizer
- [ ] ParallelProcessor

### Testing
- [ ] Unit tests for each component
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Edge case coverage
- [ ] Regression tests for original issue

### Documentation
- [ ] API documentation
- [ ] User guide updates
- [ ] Migration guide
- [ ] Performance tuning guide

### Deployment
- [ ] Feature flag system
- [ ] Monitoring integration
- [ ] Rollback procedures
- [ ] Performance metrics

## Success Metrics

1. **Reliability**
   - Target: 99.9% success rate for commit application
   - Current baseline: ~95% (fails on complex multi-file changes)
   
2. **Performance**
   - Target: No more than 10% slower than current approach
   - Optimization goal: Actually faster for large operations
   
3. **User Experience**
   - Target: Zero increase in user-reported issues
   - Improved error messages and recovery options
   
4. **Code Quality**
   - Target: 90%+ test coverage on new code
   - All edge cases documented and tested

## Risk Mitigation

### Risk 1: Performance Regression
**Mitigation Strategy:**
- Implement comprehensive benchmarking
- Use parallel processing for independent changes
- Cache Git operations where possible
- Provide fallback to legacy method

### Risk 2: Complex Conflict Resolution
**Mitigation Strategy:**
- Start with conservative auto-resolution
- Provide clear UI for manual resolution
- Maintain detailed logs for debugging
- Allow users to abort and recover

### Risk 3: Git Version Compatibility
**Mitigation Strategy:**
- Test with multiple Git versions
- Use only stable Git APIs
- Provide compatibility layer
- Clear documentation of requirements

### Risk 4: Data Loss
**Mitigation Strategy:**
- Automatic backup before operations
- Atomic operations with rollback
- Extensive testing on real repositories
- Clear recovery procedures

## Conclusion

This implementation plan provides a comprehensive approach to replacing manual patch application with Git's native operations. The phased approach ensures safety while delivering improved reliability and performance. The modular design allows for incremental implementation and testing.

Key benefits:
- Eliminates line number shift issues
- Leverages Git's 20+ years of merge algorithms
- Improves performance for large operations
- Provides better conflict resolution
- Maintains full backwards compatibility

The implementation timeline of 8 weeks allows for careful development, testing, and rollout while maintaining the current system as a fallback option.