"""Code diff analysis utilities."""

import re
from typing import Dict, List, Set
from ..models import Commit


class DiffAnalyzer:
    """Analyzes code diffs to extract meaningful patterns and relationships."""
    
    @staticmethod
    def extract_modified_functions(diff: str) -> List[str]:
        """Extract function names that were modified in the diff."""
        functions = []
        
        # Common function definition patterns for different languages
        patterns = [
            r'^\+.*(?:def|function|func)\s+(\w+)',  # Python, JS, Go
            r'^\+.*(?:public|private|protected)?\s*\w*\s*(\w+)\s*\(',  # Java, C#
            r'^\+.*(\w+)\s*:\s*function',  # JavaScript object methods
            r'^\+.*const\s+(\w+)\s*=.*=>',  # Arrow functions
        ]
        
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        functions.append(match.group(1))
        
        return list(set(functions))  # Remove duplicates
    
    @staticmethod
    def extract_modified_classes(diff: str) -> List[str]:
        """Extract class names that were modified in the diff."""
        classes = []
        
        patterns = [
            r'^\+.*class\s+(\w+)',  # Python, Java, C#
            r'^\+.*interface\s+(\w+)',  # TypeScript, Java
            r'^\+.*struct\s+(\w+)',  # Go, C
        ]
        
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        classes.append(match.group(1))
        
        return list(set(classes))
    
    @staticmethod
    def get_file_extensions(commits: List[Commit]) -> Dict[str, int]:
        """Get frequency count of file extensions across commits."""
        extensions = {}
        
        for commit in commits:
            for file_path in commit.files:
                if '.' in file_path:
                    ext = file_path.split('.')[-1].lower()
                    extensions[ext] = extensions.get(ext, 0) + 1
        
        return extensions
    
    @staticmethod
    def calculate_file_overlap(commit1: Commit, commit2: Commit) -> float:
        """Calculate the file overlap ratio between two commits."""
        files1 = set(commit1.files)
        files2 = set(commit2.files)
        
        if not files1 and not files2:
            return 0.0
        
        intersection = files1.intersection(files2)
        union = files1.union(files2)
        
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def get_common_files(commits: List[Commit]) -> Set[str]:
        """Get files that are common across multiple commits in the list."""
        if not commits:
            return set()
        
        common_files = set(commits[0].files)
        for commit in commits[1:]:
            common_files = common_files.intersection(set(commit.files))
        
        return common_files
    
    @staticmethod
    def analyze_change_type(commit: Commit) -> str:
        """Analyze the type of change based on the diff and files."""
        diff_lower = commit.diff.lower()
        files = [f.lower() for f in commit.files]
        
        # Test files
        if any('test' in f or 'spec' in f for f in files):
            return 'test'
        
        # Documentation
        if any(f.endswith(('.md', '.txt', '.rst')) for f in files):
            return 'docs'
        
        # Configuration files
        config_patterns = ['.json', '.yml', '.yaml', '.toml', '.ini', '.config']
        if any(f.endswith(tuple(config_patterns)) for f in files):
            return 'chore'
        
        # Style/formatting changes (high ratio of whitespace changes)
        lines = commit.diff.split('\n')
        whitespace_changes = sum(1 for line in lines if re.match(r'^[+-]\s*$', line))
        total_changes = len([line for line in lines if line.startswith(('+', '-'))])
        
        if total_changes > 0 and whitespace_changes / total_changes > 0.3:
            return 'style'
        
        # Bug fixes
        if any(word in diff_lower for word in ['fix', 'bug', 'error', 'issue']):
            return 'fix'
        
        # New features
        if any(word in diff_lower for word in ['add', 'new', 'feature', 'implement']):
            return 'feat'
        
        # Refactoring
        if any(word in diff_lower for word in ['refactor', 'restructure', 'reorganize']):
            return 'refactor'
        
        # Default to feat for new additions, fix for modifications
        if commit.insertions > commit.deletions * 2:
            return 'feat'
        
        return 'refactor'