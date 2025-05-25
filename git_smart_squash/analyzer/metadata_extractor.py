"""Commit metadata extraction utilities."""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from ..models import Commit


class MetadataExtractor:
    """Extracts and analyzes metadata from commits."""
    
    @staticmethod
    def extract_conventional_commit_info(message: str) -> Tuple[str, str, str]:
        """Extract type, scope, and description from conventional commit message."""
        # Pattern for conventional commits: type(scope): description
        pattern = r'^(\w+)(?:\(([^)]+)\))?\s*:\s*(.+)$'
        match = re.match(pattern, message.strip())
        
        if match:
            commit_type = match.group(1).lower()
            scope = match.group(2) or ""
            description = match.group(3)
            return commit_type, scope, description
        
        # Fallback: try to extract type from beginning of message
        type_pattern = r'^(feat|feature|fix|docs|style|refactor|test|chore|perf|ci|build|revert)\b'
        type_match = re.match(type_pattern, message.strip(), re.IGNORECASE)
        
        if type_match:
            return type_match.group(1).lower(), "", message[len(type_match.group(1)):].strip()
        
        return "", "", message.strip()
    
    @staticmethod
    def group_by_time_window(commits: List[Commit], window_seconds: int = 1800) -> List[List[Commit]]:
        """Group commits that are within a time window of each other."""
        if not commits:
            return []
        
        # Sort commits by timestamp
        sorted_commits = sorted(commits, key=lambda c: c.timestamp)
        groups = []
        current_group = [sorted_commits[0]]
        
        for commit in sorted_commits[1:]:
            # Check if this commit is within the time window of the last commit in current group
            time_diff = (commit.timestamp - current_group[-1].timestamp).total_seconds()
            
            if time_diff <= window_seconds:
                current_group.append(commit)
            else:
                groups.append(current_group)
                current_group = [commit]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    @staticmethod
    def analyze_commit_patterns(commits: List[Commit]) -> Dict[str, any]:
        """Analyze patterns in commit history."""
        if not commits:
            return {}
        
        # Time analysis
        timestamps = [c.timestamp for c in commits]
        time_span = max(timestamps) - min(timestamps)
        avg_time_between = time_span / len(commits) if len(commits) > 1 else timedelta(0)
        
        # Size analysis
        sizes = [c.insertions + c.deletions for c in commits]
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        
        # File analysis
        all_files = set()
        for commit in commits:
            all_files.update(commit.files)
        
        # Author analysis
        authors = [c.author for c in commits]
        author_count = len(set(authors))
        
        # Message analysis
        messages = [c.message for c in commits]
        avg_message_length = sum(len(m) for m in messages) / len(messages) if messages else 0
        
        # WIP/temp commit detection
        temp_patterns = [
            r'\bwip\b', r'\btemp\b', r'\btmp\b', r'\bfixup\b', r'\bsquash\b',
            r'\btodo\b', r'\btest\b.*commit', r'^\s*\.\s*$', r'^\s*fix\s*$'
        ]
        temp_commits = []
        for commit in commits:
            message_lower = commit.message.lower()
            if any(re.search(pattern, message_lower) for pattern in temp_patterns):
                temp_commits.append(commit)
        
        return {
            'total_commits': len(commits),
            'time_span_hours': time_span.total_seconds() / 3600,
            'avg_time_between_minutes': avg_time_between.total_seconds() / 60,
            'avg_commit_size': avg_size,
            'total_files_touched': len(all_files),
            'unique_authors': author_count,
            'avg_message_length': avg_message_length,
            'temp_commits': len(temp_commits),
            'temp_commit_ratio': len(temp_commits) / len(commits),
            'most_active_author': max(set(authors), key=authors.count) if authors else None
        }
    
    @staticmethod
    def detect_commit_dependencies(commits: List[Commit]) -> List[Tuple[Commit, Commit]]:
        """Detect potential dependencies between commits based on file overlap and timing."""
        dependencies = []
        
        for i, commit1 in enumerate(commits):
            for commit2 in commits[i+1:]:
                # Check if commit2 modifies files that commit1 also modified
                common_files = set(commit1.files).intersection(set(commit2.files))
                
                if common_files:
                    # Check if they're close in time (within 1 hour)
                    time_diff = abs((commit2.timestamp - commit1.timestamp).total_seconds())
                    if time_diff <= 3600:  # 1 hour
                        dependencies.append((commit1, commit2))
        
        return dependencies
    
    @staticmethod
    def extract_issue_references(message: str) -> List[str]:
        """Extract issue/ticket references from commit message."""
        patterns = [
            r'#(\d+)',  # GitHub style #123
            r'(?:fixes?|closes?|resolves?)\s+#(\d+)',  # fixes #123
            r'(?:fixes?|closes?|resolves?)\s+(\w+-\d+)',  # fixes JIRA-123
            r'(\w+-\d+)',  # Direct JIRA-style references
        ]
        
        references = []
        message_lower = message.lower()
        
        for pattern in patterns:
            matches = re.findall(pattern, message_lower, re.IGNORECASE)
            references.extend(matches)
        
        return list(set(references))  # Remove duplicates
    
    @staticmethod
    def calculate_commit_similarity(commit1: Commit, commit2: Commit) -> float:
        """Calculate similarity score between two commits based on multiple factors."""
        scores = []
        
        # File overlap similarity
        files1 = set(commit1.files)
        files2 = set(commit2.files)
        if files1 or files2:
            file_similarity = len(files1.intersection(files2)) / len(files1.union(files2))
            scores.append(file_similarity * 0.4)  # 40% weight
        
        # Message similarity (simple token overlap)
        words1 = set(commit1.message.lower().split())
        words2 = set(commit2.message.lower().split())
        if words1 or words2:
            message_similarity = len(words1.intersection(words2)) / len(words1.union(words2))
            scores.append(message_similarity * 0.2)  # 20% weight
        
        # Author similarity
        author_similarity = 1.0 if commit1.author == commit2.author else 0.0
        scores.append(author_similarity * 0.1)  # 10% weight
        
        # Time proximity (within 2 hours gets full score, decays after that)
        time_diff_hours = abs((commit2.timestamp - commit1.timestamp).total_seconds()) / 3600
        time_similarity = max(0, 1 - time_diff_hours / 24)  # Decay over 24 hours
        scores.append(time_similarity * 0.3)  # 30% weight
        
        return sum(scores)