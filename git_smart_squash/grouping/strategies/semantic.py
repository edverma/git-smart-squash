"""Semantic similarity-based grouping strategy."""

from typing import List, Tuple
from ...models import Commit, CommitGroup, GroupingConfig
from ...analyzer.metadata_extractor import MetadataExtractor
from ...analyzer.diff_analyzer import DiffAnalyzer


class SemanticGrouping:
    """Groups commits based on semantic similarity of messages and changes."""
    
    def __init__(self, config: GroupingConfig):
        self.config = config
        self.metadata_extractor = MetadataExtractor()
        self.diff_analyzer = DiffAnalyzer()
    
    def group_commits(self, commits: List[Commit]) -> List[CommitGroup]:
        """Group commits based on semantic similarity."""
        if len(commits) < 2:
            return []
        
        # Calculate similarity matrix
        similarity_matrix = self._calculate_similarity_matrix(commits)
        
        # Find groups based on similarity threshold
        groups = self._cluster_by_similarity(commits, similarity_matrix)
        
        # Convert to CommitGroup objects
        commit_groups = []
        for i, group_commits in enumerate(groups):
            if len(group_commits) > 1:  # Only create groups with multiple commits
                group = self._create_commit_group(f"semantic_group_{i}", group_commits)
                commit_groups.append(group)
        
        return commit_groups
    
    def _calculate_similarity_matrix(self, commits: List[Commit]) -> List[List[float]]:
        """Calculate similarity scores between all pairs of commits."""
        n = len(commits)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                similarity = self.metadata_extractor.calculate_commit_similarity(
                    commits[i], commits[j]
                )
                matrix[i][j] = similarity
                matrix[j][i] = similarity
        
        return matrix
    
    def _cluster_by_similarity(self, commits: List[Commit], similarity_matrix: List[List[float]]) -> List[List[Commit]]:
        """Cluster commits based on similarity threshold using simple greedy approach."""
        n = len(commits)
        visited = [False] * n
        clusters = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # Start a new cluster
            cluster = [commits[i]]
            visited[i] = True
            
            # Find all commits similar to this one
            for j in range(n):
                if not visited[j] and similarity_matrix[i][j] >= self.config.similarity_threshold:
                    cluster.append(commits[j])
                    visited[j] = True
            
            clusters.append(cluster)
        
        return clusters
    
    def _create_commit_group(self, group_id: str, commits: List[Commit]) -> CommitGroup:
        """Create a CommitGroup from semantically similar commits."""
        if not commits:
            raise ValueError("Cannot create group from empty commit list")
        
        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        
        # Calculate aggregated stats
        all_files = set()
        total_insertions = 0
        total_deletions = 0
        
        for commit in commits:
            all_files.update(commit.files)
            total_insertions += commit.insertions
            total_deletions += commit.deletions
        
        # Analyze semantic patterns
        semantic_features = self._analyze_semantic_features(commits)
        
        # Determine primary commit type
        primary_type = semantic_features['primary_type']
        
        # Generate rationale
        rationale = f"semantic_similarity: {len(commits)} commits with similar {semantic_features['similarity_reason']}"
        
        # Generate message based on semantic analysis
        suggested_message = self._generate_semantic_message(semantic_features, all_files)
        
        # Extract scope
        scope = semantic_features.get('common_scope', "")
        
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
    
    def _analyze_semantic_features(self, commits: List[Commit]) -> dict:
        """Analyze semantic features of a group of commits."""
        messages = [c.message.lower() for c in commits]
        
        # Find common words
        all_words = []
        for message in messages:
            all_words.extend(message.split())
        
        word_counts = {}
        for word in all_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Find words that appear in multiple commits
        common_words = [word for word, count in word_counts.items() if count > 1 and len(word) > 2]
        
        # Analyze commit types
        commit_types = [self.diff_analyzer.analyze_change_type(c) for c in commits]
        primary_type = max(set(commit_types), key=commit_types.count)
        
        # Find similarity reason
        if common_words:
            similarity_reason = f"messages (common terms: {', '.join(common_words[:3])})"
        else:
            # Check for file-based similarity
            file_overlap = len(set.intersection(*[set(c.files) for c in commits]))
            if file_overlap > 0:
                similarity_reason = "file modifications"
            else:
                similarity_reason = "change patterns"
        
        # Extract common scope from messages
        common_scope = ""
        scope_patterns = [r'\(([^)]+)\)', r'^\w+\s*:\s*(\w+)']
        for commit in commits:
            for pattern in scope_patterns:
                import re
                match = re.search(pattern, commit.message)
                if match:
                    scope_candidate = match.group(1)
                    if not common_scope:
                        common_scope = scope_candidate
                    elif common_scope != scope_candidate:
                        common_scope = ""
                        break
        
        return {
            'common_words': common_words,
            'primary_type': primary_type,
            'similarity_reason': similarity_reason,
            'common_scope': common_scope,
            'type_distribution': commit_types
        }
    
    def _generate_semantic_message(self, features: dict, files: set) -> str:
        """Generate a commit message based on semantic analysis."""
        primary_type = features['primary_type']
        common_words = features['common_words']
        
        if common_words:
            # Use common words to create a meaningful message
            key_words = [w for w in common_words if w not in ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']]
            if key_words:
                description = ' '.join(key_words[:2])
                return f"{primary_type}: {description}"
        
        # Fallback to file-based description
        if len(files) <= 3:
            file_desc = ', '.join(sorted(files))
        else:
            file_desc = f"{len(files)} files"
        
        return f"{primary_type}: Update {file_desc}"