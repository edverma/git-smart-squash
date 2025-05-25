"""Dependency-based grouping strategy."""

from typing import List, Dict, Set, Tuple
from ...models import Commit, CommitGroup, GroupingConfig
from ...analyzer.metadata_extractor import MetadataExtractor
from ...analyzer.diff_analyzer import DiffAnalyzer


class DependencyGrouping:
    """Groups commits based on logical dependencies and build-upon relationships."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.metadata_extractor = MetadataExtractor()
        self.diff_analyzer = DiffAnalyzer()
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits based on dependency chains."""
        if len(commits) < 2:
            return []
        
        # Detect dependencies between commits
        dependencies = self.metadata_extractor.detect_commit_dependencies(commits)
        
        # Build dependency chains
        chains = self._build_dependency_chains(commits, dependencies)
        
        # Convert chains to CommitGroups
        groups = []
        for i, chain in enumerate(chains):
            if len(chain) > 1:  # Only create groups with multiple commits
                group = self._create_commit_group(f"dependency_group_{i}", chain)
                groups.append(group)
        
        return groups
    
    def _build_dependency_chains(self, commits: List[Commit], dependencies: List[Tuple[Commit, Commit]]) -> List[List[Commit]]:
        """Build chains of dependent commits."""
        # Create adjacency list for dependencies
        commit_graph = {commit.hash: [] for commit in commits}
        reverse_graph = {commit.hash: [] for commit in commits}
        
        for commit1, commit2 in dependencies:
            commit_graph[commit1.hash].append(commit2)
            reverse_graph[commit2.hash].append(commit1)
        
        # Find chains using DFS
        visited = set()
        chains = []
        
        # Start from commits with no dependencies (roots)
        roots = [commit for commit in commits if not reverse_graph[commit.hash]]
        
        for root in roots:
            if root.hash not in visited:
                chain = []
                self._dfs_chain(root, commit_graph, visited, chain, commits)
                if len(chain) > 1:
                    chains.append(chain)
        
        # Handle any remaining unvisited commits (cycles or orphans)
        for commit in commits:
            if commit.hash not in visited:
                chain = []
                self._dfs_chain(commit, commit_graph, visited, chain, commits)
                if len(chain) > 1:
                    chains.append(chain)
        
        return chains
    
    def _dfs_chain(self, commit: Commit, graph: Dict[str, List[Commit]], visited: Set[str], chain: List[Commit], all_commits: List[Commit]):
        """Build a dependency chain using DFS."""
        if commit.hash in visited:
            return
        
        visited.add(commit.hash)
        chain.append(commit)
        
        # Continue with dependent commits
        for dependent in graph[commit.hash]:
            if dependent.hash not in visited:
                self._dfs_chain(dependent, graph, visited, chain, all_commits)
    
    def _create_commit_group(self, group_id: str, commits: List[Commit]) -> CommitGroup:
        """Create a CommitGroup from a dependency chain."""
        if not commits:
            raise ValueError("Cannot create group from empty commit list")
        
        # Sort commits by timestamp to maintain chronological order
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        
        # Calculate aggregated stats
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Analyze the dependency pattern
        dependency_features = self._analyze_dependency_features(sorted_commits)
        
        # Determine primary commit type based on the final commit in the chain
        primary_type = self.diff_analyzer.analyze_change_type(sorted_commits[-1])
        
        # Generate rationale
        rationale = f"dependency_chain: {len(commits)} commits in logical sequence"
        if dependency_features['has_progressive_changes']:
            rationale += " with progressive development"
        
        # Generate message based on the progression
        suggested_message = self._generate_dependency_message(dependency_features, primary_type, all_files)
        
        # Extract scope from the most significant commit
        scope = self._extract_scope_from_progression(sorted_commits)
        
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
    
    def _analyze_dependency_features(self, commits: List[Commit]) -> dict:
        """Analyze features of a dependency chain."""
        features = {
            'has_progressive_changes': False,
            'incremental_files': False,
            'consistent_author': False,
            'build_pattern': False
        }
        
        # Check for progressive changes (each commit builds on the previous)
        progressive_score = 0
        for i in range(1, len(commits)):
            prev_files = set(commits[i-1].files)
            curr_files = set(commits[i].files)
            
            # If current commit modifies files from previous commit, it's progressive
            if prev_files.intersection(curr_files):
                progressive_score += 1
        
        features['has_progressive_changes'] = progressive_score >= len(commits) * 0.5
        
        # Check for incremental file additions
        all_files_so_far = set()
        incremental_count = 0
        for commit in commits:
            commit_files = set(commit.files)
            if commit_files - all_files_so_far:  # New files in this commit
                incremental_count += 1
            all_files_so_far.update(commit_files)
        
        features['incremental_files'] = incremental_count >= len(commits) * 0.7
        
        # Check for consistent author
        authors = [c.author for c in commits]
        features['consistent_author'] = len(set(authors)) == 1
        
        # Check for test/implementation patterns
        test_files = [f for commit in commits for f in commit.files if 'test' in f.lower() or 'spec' in f.lower()]
        impl_files = [f for commit in commits for f in commit.files if 'test' not in f.lower() and 'spec' not in f.lower()]
        features['build_pattern'] = len(test_files) > 0 and len(impl_files) > 0
        
        return features
    
    def _generate_dependency_message(self, features: dict, primary_type: str, files: set) -> str:
        """Generate a commit message for a dependency chain."""
        if features['build_pattern']:
            return f"{primary_type}: Implement feature with tests"
        
        if features['has_progressive_changes']:
            if len(files) <= 3:
                file_desc = ', '.join(sorted(files))
                return f"{primary_type}: Iteratively develop {file_desc}"
            else:
                return f"{primary_type}: Progressively implement across {len(files)} files"
        
        if features['incremental_files']:
            return f"{primary_type}: Build feature incrementally"
        
        # Fallback
        return f"{primary_type}: Complete related changes"
    
    def _extract_scope_from_progression(self, commits: List[Commit]) -> str:
        """Extract scope from the progression of commits."""
        # Look at the final commit's scope as it represents the complete change
        final_commit = commits[-1]
        
        # Try to extract from conventional commit format
        type_info = self.metadata_extractor.extract_conventional_commit_info(final_commit.message)
        if type_info[1]:  # scope exists
            return type_info[1]
        
        # Fallback to file-based scope extraction
        all_files = set()
        for commit in commits:
            all_files.update(commit.files)
        
        # Find common directory
        if all_files:
            file_list = list(all_files)
            if len(file_list) == 1:
                parts = file_list[0].split('/')
                if len(parts) > 1:
                    return parts[-2]
            else:
                # Find common prefix
                common_parts = []
                first_parts = file_list[0].split('/')
                
                for i, part in enumerate(first_parts[:-1]):
                    if all(len(f.split('/')) > i and f.split('/')[i] == part for f in file_list):
                        common_parts.append(part)
                    else:
                        break
                
                if common_parts:
                    return common_parts[-1]
        
        return ""