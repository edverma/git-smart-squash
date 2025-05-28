"""Unified commit analysis functionality."""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict, Counter

from .models import Commit


class CommitAnalyzer:
    """Analyzes commits for patterns, changes, and relationships."""
    
    # Diff analysis patterns
    FUNCTION_PATTERN = re.compile(r'^\+?\s*(?:def|function|func|fn)\s+(\w+)', re.MULTILINE)
    CLASS_PATTERN = re.compile(r'^\+?\s*(?:class|struct|interface|type)\s+(\w+)', re.MULTILINE)
    
    # Conventional commit pattern
    CONVENTIONAL_PATTERN = re.compile(
        r'^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert)(\(([^)]+)\))?(!)?:\s*(.+)',
        re.IGNORECASE
    )
    
    # Issue reference patterns
    ISSUE_PATTERNS = [
        re.compile(r'#(\d+)'),
        re.compile(r'(?:fixes|closes|resolves)\s+#(\d+)', re.IGNORECASE),
        re.compile(r'(?:issue|bug)\s+#?(\d+)', re.IGNORECASE),
    ]
    
    # Change type keywords
    CHANGE_KEYWORDS = {
        'feat': ['add', 'implement', 'create', 'introduce', 'new'],
        'fix': ['fix', 'repair', 'correct', 'resolve', 'patch', 'bug'],
        'docs': ['document', 'docs', 'readme', 'comment', 'docstring'],
        'test': ['test', 'spec', 'coverage', 'unit', 'integration'],
        'refactor': ['refactor', 'restructure', 'reorganize', 'optimize', 'clean'],
        'style': ['format', 'style', 'whitespace', 'prettier', 'eslint'],
        'chore': ['update', 'upgrade', 'dependency', 'deps', 'package'],
        'build': ['build', 'compile', 'bundle', 'webpack', 'rollup'],
        'ci': ['ci', 'pipeline', 'workflow', 'github', 'travis', 'jenkins'],
    }
    
    def extract_modified_functions(self, diff: str) -> List[str]:
        """Extract function names from a diff."""
        added_functions = []
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                match = self.FUNCTION_PATTERN.search(line)
                if match:
                    added_functions.append(match.group(1))
        return added_functions
    
    def extract_modified_classes(self, diff: str) -> List[str]:
        """Extract class names from a diff."""
        added_classes = []
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                match = self.CLASS_PATTERN.search(line)
                if match:
                    added_classes.append(match.group(1))
        return added_classes
    
    def analyze_change_type(self, commit: Commit) -> str:
        """Determine the type of change from commit content."""
        message_lower = commit.message.lower()
        
        # Check conventional commit format first
        conv_info = self.extract_conventional_commit_info(commit.message)
        if conv_info[0]:
            return conv_info[0]
        
        # Analyze based on keywords
        for change_type, keywords in self.CHANGE_KEYWORDS.items():
            if any(keyword in message_lower for keyword in keywords):
                return change_type
        
        # Analyze based on files
        if commit.files:
            # Check for test files
            if any('test' in f or 'spec' in f for f in commit.files):
                return 'test'
            
            # Check for documentation
            if any(f.endswith(('.md', '.rst', '.txt')) for f in commit.files):
                return 'docs'
            
            # Check for config/build files
            build_files = ['package.json', 'requirements.txt', 'Cargo.toml', 'go.mod']
            if any(any(bf in f for bf in build_files) for f in commit.files):
                return 'build'
        
        # Default based on diff size
        if commit.deletions > commit.insertions:
            return 'refactor'
        
        return 'feat'  # Default to feature
    
    def extract_conventional_commit_info(self, message: str) -> Tuple[Optional[str], Optional[str], bool, str]:
        """Extract conventional commit information."""
        first_line = message.split('\n')[0]
        match = self.CONVENTIONAL_PATTERN.match(first_line)
        
        if match:
            commit_type = match.group(1).lower()
            scope = match.group(3) if match.group(3) else None
            breaking = bool(match.group(4))
            description = match.group(5)
            return commit_type, scope, breaking, description
        
        return None, None, False, first_line
    
    def extract_issue_references(self, message: str) -> List[str]:
        """Extract issue references from commit message."""
        references = []
        for pattern in self.ISSUE_PATTERNS:
            matches = pattern.findall(message)
            references.extend(matches)
        return list(set(references))
    
    def get_file_extensions(self, commits: List[Commit]) -> Dict[str, int]:
        """Get statistics on file extensions modified."""
        extensions = defaultdict(int)
        for commit in commits:
            for file in commit.files:
                if '.' in file:
                    ext = file.split('.')[-1]
                    extensions[ext] += 1
        return dict(extensions)
    
    def get_common_files(self, commits: List[Commit]) -> Set[str]:
        """Get files that appear in multiple commits."""
        file_counts = defaultdict(int)
        for commit in commits:
            for file in commit.files:
                file_counts[file] += 1
        
        return {file for file, count in file_counts.items() if count > 1}
    
    def calculate_file_overlap(self, commit1: Commit, commit2: Commit) -> float:
        """Calculate the file overlap between two commits."""
        if not commit1.files or not commit2.files:
            return 0.0
        
        files1 = set(commit1.files)
        files2 = set(commit2.files)
        
        intersection = files1 & files2
        union = files1 | files2
        
        return len(intersection) / len(union) if union else 0.0
    
    def calculate_commit_similarity(self, commit1: Commit, commit2: Commit) -> float:
        """Calculate similarity between two commits."""
        # File overlap (40% weight)
        file_score = self.calculate_file_overlap(commit1, commit2) * 0.4
        
        # Message similarity (30% weight)
        message_score = self._calculate_message_similarity(commit1.message, commit2.message) * 0.3
        
        # Temporal proximity (20% weight)
        time_diff = abs((commit1.timestamp - commit2.timestamp).total_seconds())
        time_score = max(0, 1 - (time_diff / 3600)) * 0.2  # 1 hour window
        
        # Change type similarity (10% weight)
        type1 = self.analyze_change_type(commit1)
        type2 = self.analyze_change_type(commit2)
        type_score = 0.1 if type1 == type2 else 0
        
        return file_score + message_score + time_score + type_score
    
    def _calculate_message_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between commit messages."""
        # Simple word-based similarity
        words1 = set(msg1.lower().split())
        words2 = set(msg2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def detect_commit_dependencies(self, commits: List[Commit]) -> List[Tuple[Commit, Commit]]:
        """Detect dependencies between commits."""
        dependencies = []
        
        for i, commit in enumerate(commits):
            for j in range(i + 1, len(commits)):
                other = commits[j]
                
                # Check if commits modify the same files
                if set(commit.files) & set(other.files):
                    # Check if the later commit mentions the earlier one
                    if commit.short_hash in other.message or commit.hash[:8] in other.message:
                        dependencies.append((commit, other))
                    
                    # Check for explicit dependency keywords
                    dep_keywords = ['depends on', 'requires', 'based on', 'follows']
                    if any(keyword in other.message.lower() for keyword in dep_keywords):
                        dependencies.append((commit, other))
        
        return dependencies
    
    def group_by_time_window(self, commits: List[Commit], window_seconds: int = 1800) -> List[List[Commit]]:
        """Group commits by time window."""
        if not commits:
            return []
        
        groups = []
        current_group = [commits[0]]
        
        for i in range(1, len(commits)):
            time_diff = (commits[i].timestamp - commits[i-1].timestamp).total_seconds()
            
            if time_diff <= window_seconds:
                current_group.append(commits[i])
            else:
                groups.append(current_group)
                current_group = [commits[i]]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def analyze_commit_patterns(self, commits: List[Commit]) -> Dict:
        """Analyze patterns in commit history."""
        if not commits:
            return {
                'total_commits': 0,
                'avg_commits_per_day': 0,
                'most_active_hour': None,
                'commit_types': {},
                'file_extensions': {},
                'common_files': []
            }
        
        # Time-based analysis
        timestamps = [c.timestamp for c in commits]
        time_span = (max(timestamps) - min(timestamps)).days + 1
        
        # Hour distribution
        hours = [t.hour for t in timestamps]
        hour_counts = Counter(hours)
        most_active_hour = hour_counts.most_common(1)[0][0] if hour_counts else None
        
        # Commit type distribution
        commit_types = Counter(self.analyze_change_type(c) for c in commits)
        
        return {
            'total_commits': len(commits),
            'avg_commits_per_day': len(commits) / time_span if time_span > 0 else len(commits),
            'most_active_hour': most_active_hour,
            'commit_types': dict(commit_types),
            'file_extensions': self.get_file_extensions(commits),
            'common_files': list(self.get_common_files(commits))
        }