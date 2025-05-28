"""Unified grouping strategy implementation."""

import re
from typing import List, Dict, Set, Tuple
from datetime import timedelta
from collections import defaultdict

from ..core.models import Commit, CommitGroup, GroupingConfig
from ..core.commit_analyzer import CommitAnalyzer
from .utils import extract_scope_from_files


class UnifiedGroupingStrategy:
    """Unified implementation of all grouping strategies."""
    
    def __init__(self, config: GroupingConfig, strategy_type: str):
        self.config = config
        self.strategy_type = strategy_type
        self.commit_analyzer = CommitAnalyzer()
        
        # Validate strategy type
        valid_strategies = ["temporal", "file_overlap", "semantic", "dependency"]
        if strategy_type not in valid_strategies:
            raise ValueError(f"Invalid strategy type: {strategy_type}. Must be one of {valid_strategies}")
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits using the configured strategy."""
        if len(commits) < 2:
            return []
        
        # Apply strategy-specific grouping
        if self.strategy_type == "temporal":
            raw_groups = self._group_by_temporal(commits)
        elif self.strategy_type == "file_overlap":
            raw_groups = self._group_by_file_overlap(commits)
        elif self.strategy_type == "semantic":
            raw_groups = self._group_by_semantic(commits)
        elif self.strategy_type == "dependency":
            raw_groups = self._group_by_dependency(commits)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy_type}")
        
        # Convert to CommitGroups
        groups = []
        for i, commit_list in enumerate(raw_groups):
            if len(commit_list) > 1:
                group = self._create_commit_group(
                    f"{self.strategy_type}_group_{i}",
                    commit_list
                )
                groups.append(group)
        
        return groups
    
    def _group_by_time_window(self, commits: List[Commit], window_minutes: int) -> List[List[Commit]]:
        """Group commits within the specified time window."""
        if not commits:
            return []
        
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        groups = []
        current_group = [sorted_commits[0]]
        
        for commit in sorted_commits[1:]:
            time_diff = commit.timestamp - current_group[-1].timestamp
            if time_diff <= timedelta(minutes=window_minutes):
                current_group.append(commit)
            else:
                groups.append(current_group)
                current_group = [commit]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _group_by_temporal(self, commits: List[Commit]) -> List[List[Commit]]:
        """Group commits within time windows."""
        return self._group_by_time_window(
            commits, 
            self.config.time_window
        )
    
    def _group_by_file_overlap(self, commits: List[Commit]) -> List[List[Commit]]:
        """Group commits that modify the same files."""
        # Build file to commits mapping
        file_to_commits: Dict[str, List[Commit]] = defaultdict(list)
        for commit in commits:
            for file in commit.files:
                file_to_commits[file].append(commit)
        
        # Find connected components
        commit_groups = []
        processed = set()  # Set of commit hashes
        
        for commit in commits:
            if commit.hash in processed:
                continue
            
            # Find all commits connected through file overlap
            group = self._find_connected_commits(
                commit, file_to_commits, processed
            )
            
            if len(group) >= self.config.min_file_overlap:
                commit_groups.append(sorted(group, key=lambda c: c.timestamp))
        
        return commit_groups
    
    def _find_connected_commits(self, start_commit: Commit, 
                               file_to_commits: Dict[str, List[Commit]], 
                               processed: Set[str]) -> List[Commit]:
        """Find all commits connected to start_commit through file overlap."""
        connected = []
        stack = [start_commit]
        
        while stack:
            commit = stack.pop()
            if commit.hash in processed:
                continue
            
            processed.add(commit.hash)
            connected.append(commit)
            
            # Find commits that share files
            for file in commit.files:
                for other_commit in file_to_commits[file]:
                    if other_commit.hash not in processed:
                        stack.append(other_commit)
        
        return connected
    
    def _group_by_semantic(self, commits: List[Commit]) -> List[List[Commit]]:
        """Group commits by semantic similarity."""
        # Calculate similarity matrix
        n = len(commits)
        similarity_matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                similarity = self.commit_analyzer.calculate_commit_similarity(
                    commits[i], commits[j]
                )
                similarity_matrix[i][j] = similarity
                similarity_matrix[j][i] = similarity
        
        # Cluster by similarity threshold
        groups = []
        processed = set()
        
        for i, commit in enumerate(commits):
            if i in processed:
                continue
            
            # Find all similar commits
            group = [commit]
            processed.add(i)
            
            for j, other_commit in enumerate(commits):
                if j not in processed and similarity_matrix[i][j] >= self.config.similarity_threshold:
                    group.append(other_commit)
                    processed.add(j)
            
            if len(group) > 1:
                groups.append(sorted(group, key=lambda c: c.timestamp))
        
        return groups
    
    def _group_by_dependency(self, commits: List[Commit]) -> List[List[Commit]]:
        """Group commits based on dependency relationships."""
        # Build dependency graph
        graph = defaultdict(list)
        file_history = {}
        
        for i, commit in enumerate(commits):
            for file in commit.files:
                if file in file_history:
                    # This commit depends on the last commit that touched this file
                    graph[file_history[file]].append(i)
                file_history[file] = i
        
        # Find dependency chains
        chains = []
        visited = set()
        
        for i in range(len(commits)):
            if i not in visited:
                chain = self._build_dependency_chain(i, graph, commits, visited)
                if len(chain) > 1:
                    chains.append(chain)
        
        return chains
    
    def _build_dependency_chain(self, start: int, graph: Dict[int, List[int]], 
                               commits: List[Commit], visited: Set[int]) -> List[Commit]:
        """Build a dependency chain starting from a commit."""
        chain = []
        stack = [start]
        
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            
            visited.add(current)
            chain.append(commits[current])
            
            # Add dependent commits
            for dependent in graph[current]:
                if dependent not in visited:
                    stack.append(dependent)
        
        return sorted(chain, key=lambda c: c.timestamp)
    
    def _create_commit_group(self, group_id: str, commits: List[Commit]) -> CommitGroup:
        """Create a CommitGroup from a list of commits."""
        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        
        # Aggregate statistics
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in sorted_commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Determine primary commit type
        change_types = [self.commit_analyzer.analyze_change_type(c) for c in sorted_commits]
        type_counts = defaultdict(int)
        for ct in change_types:
            type_counts[ct] += 1
        
        primary_type = max(type_counts.items(), key=lambda x: x[1])[0]
        
        # Generate rationale based on strategy
        rationale = self._generate_rationale(sorted_commits)
        
        # Generate suggested message
        suggested_message = self._generate_suggested_message(
            primary_type, all_files, sorted_commits
        )
        
        # Extract scope
        scope = self._extract_scope(sorted_commits, all_files)
        
        return CommitGroup(
            id=group_id,
            commits=sorted_commits,
            rationale=rationale,
            suggested_message=suggested_message,
            commit_type=primary_type,
            scope=scope,
            files_touched=all_files,
            total_insertions=total_insertions,
            total_deletions=total_deletions
        )
    
    def _generate_rationale(self, commits: List[Commit]) -> str:
        """Generate rationale based on strategy type."""
        if self.strategy_type == "temporal":
            time_span = commits[-1].timestamp - commits[0].timestamp
            return f"Commits made within {self._format_time_span(time_span)}"
        
        elif self.strategy_type == "file_overlap":
            common_files = set(commits[0].files)
            for commit in commits[1:]:
                common_files &= set(commit.files)
            return f"Commits modifying {len(common_files)} common file(s)"
        
        elif self.strategy_type == "semantic":
            return "Semantically similar commits based on message and content analysis"
        
        elif self.strategy_type == "dependency":
            return "Commits form a logical dependency chain"
        
        return "Grouped commits"
    
    def _generate_suggested_message(self, commit_type: str, files: Set[str], 
                                   commits: List[Commit]) -> str:
        """Generate suggested commit message."""
        # Extract key information from commits
        if self.strategy_type == "dependency":
            # For dependency chains, focus on the final state
            final_commit = commits[-1]
            base_msg = final_commit.message.split('\n')[0]
            
            # Check if it's a progressive implementation
            if any(word in msg.lower() for msg in [c.message for c in commits] 
                   for word in ['initial', 'add', 'implement', 'complete']):
                return f"{commit_type}: complete implementation of {base_msg.lower()}"
        
        elif self.strategy_type == "semantic":
            # Find common themes
            all_messages = ' '.join(c.message.lower() for c in commits)
            common_words = self._extract_common_words(all_messages)
            if common_words:
                return f"{commit_type}: {' '.join(common_words[:3])}"
        
        # Default: use file-based description
        if len(files) == 1:
            file = list(files)[0]
            return f"{commit_type}: update {file}"
        elif len(files) <= 3:
            return f"{commit_type}: update {', '.join(sorted(files))}"
        else:
            # Find common directory
            scope = extract_scope_from_files(files)
            if scope:
                return f"{commit_type}: update {scope} module"
            return f"{commit_type}: update multiple files"
    
    def _extract_scope(self, commits: List[Commit], files: Set[str]) -> str:
        """Extract scope from commits and files."""
        # Try conventional commit format first
        for commit in commits:
            type_info = self.commit_analyzer.extract_conventional_commit_info(commit.message)
            if type_info[1]:  # scope exists
                return type_info[1]
        
        # Fallback to file-based extraction
        return extract_scope_from_files(files)
    
    def _format_time_span(self, delta: timedelta) -> str:
        """Format time span in human-readable format."""
        total_seconds = int(delta.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''}"
    
    def _extract_common_words(self, text: str) -> List[str]:
        """Extract meaningful common words from text."""
        # Remove common words and filter
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 
                     'to', 'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are'}
        
        words = re.findall(r'\w+', text.lower())
        word_counts = defaultdict(int)
        
        for word in words:
            if len(word) > 2 and word not in stop_words:
                word_counts[word] += 1
        
        # Return most common meaningful words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:5]]