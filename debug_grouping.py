#!/usr/bin/env python3
"""
Debug script for understanding why commits aren't being grouped.

This script helps diagnose grouping issues by:
1. Running each grouping strategy individually
2. Showing what groups each strategy creates
3. Showing the deduplication process
4. Analyzing potential issues with thresholds and scoring

Usage:
    python debug_grouping.py
"""

import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_smart_squash.models import Commit, GroupingConfig
from git_smart_squash.grouping.grouping_engine import GroupingEngine
from git_smart_squash.grouping.strategies.file_overlap import FileOverlapGrouping
from git_smart_squash.grouping.strategies.temporal import TemporalGrouping
from git_smart_squash.grouping.strategies.semantic import SemanticGrouping
from git_smart_squash.grouping.strategies.dependency import DependencyGrouping
from git_smart_squash.config.constants import DEFAULT_SIMILARITY_THRESHOLD


def create_test_commits() -> List[Commit]:
    """Create a set of test commits that should demonstrate grouping issues."""
    base_time = datetime.now()
    
    commits = [
        # Related commits that should group together (file overlap)
        Commit(
            hash="abc123", short_hash="abc123", author="Test User", email="test@example.com",
            timestamp=base_time, message="fix: update user authentication",
            files=["src/auth/login.py", "src/auth/middleware.py"], 
            insertions=15, deletions=3, diff="", parent_hash="prev1"
        ),
        Commit(
            hash="def456", short_hash="def456", author="Test User", email="test@example.com",
            timestamp=base_time, message="fix: handle auth edge cases",
            files=["src/auth/login.py", "tests/test_auth.py"], 
            insertions=8, deletions=2, diff="", parent_hash="abc123"
        ),
        Commit(
            hash="ghi789", short_hash="ghi789", author="Test User", email="test@example.com",
            timestamp=base_time, message="fix: auth token validation",
            files=["src/auth/middleware.py", "src/auth/tokens.py"], 
            insertions=12, deletions=1, diff="", parent_hash="def456"
        ),
        
        # Semantically related commits
        Commit(
            hash="jkl012", short_hash="jkl012", author="Test User", email="test@example.com",
            timestamp=base_time, message="feat: add user profile page",
            files=["src/ui/profile.py", "templates/profile.html"], 
            insertions=45, deletions=0, diff="", parent_hash="ghi789"
        ),
        Commit(
            hash="mno345", short_hash="mno345", author="Test User", email="test@example.com",
            timestamp=base_time, message="feat: add user settings to profile",
            files=["src/ui/profile.py", "src/ui/settings.py"], 
            insertions=23, deletions=5, diff="", parent_hash="jkl012"
        ),
        
        # Unrelated commit
        Commit(
            hash="pqr678", short_hash="pqr678", author="Test User", email="test@example.com",
            timestamp=base_time, message="docs: update README",
            files=["README.md"], 
            insertions=3, deletions=1, diff="", parent_hash="mno345"
        ),
    ]
    
    return commits


def print_separator(title: str, width: int = 80):
    """Print a formatted separator with title."""
    padding = (width - len(title) - 2) // 2
    print("\n" + "=" * padding + f" {title} " + "=" * padding)


def print_commit_summary(commits: List[Commit]):
    """Print a summary of all commits."""
    print(f"Total commits: {len(commits)}")
    for i, commit in enumerate(commits):
        files_str = ", ".join(commit.files[:2]) + ("..." if len(commit.files) > 2 else "")
        print(f"  {i+1}. {commit.short_hash}: {commit.message[:50]}...")
        print(f"     Files: {files_str}")
        print(f"     Changes: +{commit.insertions}/-{commit.deletions}")


def analyze_individual_strategy(strategy_name: str, strategy, commits: List[Commit]):
    """Analyze results from a single grouping strategy."""
    print_separator(f"{strategy_name.upper()} STRATEGY")
    
    try:
        groups = strategy.group_commits(commits)
        print(f"Groups created: {len(groups)}")
        
        if not groups:
            print("  No groups created by this strategy")
            return groups
        
        for i, group in enumerate(groups):
            print(f"\n  Group {i+1} ({group.id}):")
            print(f"    Commits: {len(group.commits)}")
            print(f"    Rationale: {group.rationale}")
            print(f"    Confidence: {group.confidence:.2f}")
            
            for commit in group.commits:
                print(f"      - {commit.short_hash}: {commit.message[:40]}...")
            
            print(f"    Files touched: {len(group.files_touched)}")
            if len(group.files_touched) <= 5:
                print(f"      {', '.join(sorted(group.files_touched))}")
            
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        groups = []
    
    return groups


def analyze_file_overlap_details(commits: List[Commit], config: GroupingConfig):
    """Analyze file overlap patterns in detail."""
    print_separator("FILE OVERLAP ANALYSIS")
    
    # Build file-to-commits mapping
    file_to_commits = {}
    for commit in commits:
        for file_path in commit.files:
            if file_path not in file_to_commits:
                file_to_commits[file_path] = []
            file_to_commits[file_path].append(commit)
    
    print("File overlap patterns:")
    for file_path, file_commits in file_to_commits.items():
        if len(file_commits) > 1:
            print(f"  {file_path}: {len(file_commits)} commits")
            for commit in file_commits:
                print(f"    - {commit.short_hash}: {commit.message[:30]}...")
    
    print(f"\nConfiguration:")
    print(f"  min_file_overlap: {config.min_file_overlap}")
    
    # Check pairwise file overlaps
    print(f"\nPairwise file overlaps:")
    potential_groups = []
    for i, commit1 in enumerate(commits):
        for j, commit2 in enumerate(commits[i+1:], i+1):
            overlap = len(set(commit1.files) & set(commit2.files))
            if overlap > 0:
                print(f"  {commit1.short_hash} <-> {commit2.short_hash}: {overlap} shared files")
                shared_files = set(commit1.files) & set(commit2.files)
                print(f"    Shared: {', '.join(shared_files)}")
                potential_groups.append((commit1, commit2, overlap))
    
    print(f"\nExpected groups based on file overlap:")
    # Group commits that share files using a simple approach
    visited = set()
    expected_groups = []
    for commit1, commit2, overlap in potential_groups:
        if commit1.hash not in visited and commit2.hash not in visited:
            group = [commit1, commit2]
            visited.add(commit1.hash)
            visited.add(commit2.hash)
            
            # Find other commits that share files with these
            for commit3 in commits:
                if commit3.hash not in visited:
                    for group_commit in group:
                        if set(commit3.files) & set(group_commit.files):
                            group.append(commit3)
                            visited.add(commit3.hash)
                            break
            
            expected_groups.append(group)
    
    for i, group in enumerate(expected_groups):
        print(f"  Expected Group {i+1}: {[c.short_hash for c in group]}")
        shared_files = set.intersection(*[set(c.files) for c in group])
        print(f"    Common files: {', '.join(shared_files) if shared_files else 'None (but some overlap exists)'}")
    
    print(f"\nDebugging file overlap calculation:")
    from git_smart_squash.analyzer.diff_analyzer import DiffAnalyzer
    diff_analyzer = DiffAnalyzer()
    for commit1, commit2, overlap in potential_groups:
        calculated_overlap = diff_analyzer.calculate_file_overlap(commit1, commit2)
        threshold = config.min_file_overlap / max(len(commit1.files), len(commit2.files), 1)
        print(f"  {commit1.short_hash} <-> {commit2.short_hash}:")
        print(f"    Actual overlap: {overlap} files")
        print(f"    Calculated overlap: {calculated_overlap:.3f}")
        print(f"    Threshold: {threshold:.3f}")
        print(f"    Would group? {calculated_overlap >= threshold}")


def analyze_semantic_similarity(commits: List[Commit], config: GroupingConfig):
    """Analyze semantic similarity between commits."""
    print_separator("SEMANTIC SIMILARITY ANALYSIS")
    
    print(f"Configuration:")
    print(f"  similarity_threshold: {config.similarity_threshold}")
    print(f"  Default from constants: {DEFAULT_SIMILARITY_THRESHOLD}")
    
    # Analyze message similarity patterns
    print(f"\nMessage similarity analysis:")
    for i, commit1 in enumerate(commits):
        for j, commit2 in enumerate(commits[i+1:], i+1):
            # Simple similarity calculation (similar to what's in the code)
            words1 = set(commit1.message.lower().split())
            words2 = set(commit2.message.lower().split())
            
            # Remove common words
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            words1 = words1 - common_words
            words2 = words2 - common_words
            
            if words1 and words2:
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                similarity = intersection / union if union > 0 else 0.0
                
                if similarity > 0.1:  # Show any meaningful similarity
                    print(f"  {commit1.short_hash} <-> {commit2.short_hash}: {similarity:.2f}")
                    print(f"    Shared words: {', '.join(words1 & words2)}")
                    print(f"    Above threshold? {similarity >= config.similarity_threshold}")


def analyze_deduplication_process(all_groups: List, engine: GroupingEngine):
    """Analyze the deduplication process in detail."""
    print_separator("DEDUPLICATION ANALYSIS")
    
    print(f"Groups before deduplication: {len(all_groups)}")
    
    if not all_groups:
        print("  No groups to deduplicate")
        return []
    
    # Show scoring for each group
    print("\nGroup scoring:")
    for i, group in enumerate(all_groups):
        score = engine._score_group(group)
        print(f"  Group {i+1}: score={score:.3f}, commits={len(group.commits)}")
        print(f"    Rationale: {group.rationale}")
        print(f"    Commit hashes: {[c.short_hash for c in group.commits]}")
    
    # Sort groups by quality score (as done in deduplication)
    sorted_groups = sorted(all_groups, key=engine._score_group, reverse=True)
    
    print(f"\nGroups after sorting by score:")
    for i, group in enumerate(sorted_groups):
        score = engine._score_group(group)
        print(f"  {i+1}. Score={score:.3f}, commits={[c.short_hash for c in group.commits]}")
    
    # Simulate deduplication process
    final_groups = []
    used_commits = set()
    rejected_groups = []
    
    for group in sorted_groups:
        group_commits = set(c.hash for c in group.commits)
        
        if group_commits & used_commits:
            rejected_groups.append((group, "overlapping commits"))
            continue
            
        final_groups.append(group)
        used_commits.update(group_commits)
    
    print(f"\nDeduplication results:")
    print(f"  Final groups: {len(final_groups)}")
    print(f"  Rejected groups: {len(rejected_groups)}")
    
    if rejected_groups:
        print(f"\nRejected groups:")
        for group, reason in rejected_groups:
            print(f"    - {reason}: {[c.short_hash for c in group.commits]}")
    
    return final_groups


def analyze_configuration_impact(commits: List[Commit]):
    """Analyze how different configuration values would affect grouping."""
    print_separator("CONFIGURATION IMPACT ANALYSIS")
    
    # Test different similarity thresholds
    print("Testing different similarity thresholds:")
    thresholds = [0.3, 0.5, 0.7, 0.9]
    
    for threshold in thresholds:
        config = GroupingConfig(similarity_threshold=threshold)
        semantic_strategy = SemanticGrouping(config)
        groups = semantic_strategy.group_commits(commits)
        print(f"  threshold={threshold}: {len(groups)} semantic groups")
    
    # Test different file overlap requirements
    print(f"\nTesting different file overlap minimums:")
    overlaps = [1, 2, 3]
    
    for overlap in overlaps:
        config = GroupingConfig(min_file_overlap=overlap)
        file_strategy = FileOverlapGrouping(config)
        groups = file_strategy.group_commits(commits)
        print(f"  min_overlap={overlap}: {len(groups)} file-based groups")


def run_full_debug_analysis():
    """Run the complete debug analysis."""
    print("GIT SMART SQUASH - GROUPING DEBUG ANALYSIS")
    print("=========================================")
    
    # Create test data
    commits = create_test_commits()
    config = GroupingConfig(similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD)
    
    # Print commit summary
    print_separator("TEST COMMITS")
    print_commit_summary(commits)
    
    # Initialize strategies
    engine = GroupingEngine(config)
    file_strategy = FileOverlapGrouping(config)
    temporal_strategy = TemporalGrouping(config)
    semantic_strategy = SemanticGrouping(config)
    dependency_strategy = DependencyGrouping(config)
    
    # Analyze each strategy individually
    all_strategy_groups = []
    
    file_groups = analyze_individual_strategy("File Overlap", file_strategy, commits)
    all_strategy_groups.extend(file_groups)
    
    temporal_groups = analyze_individual_strategy("Temporal", temporal_strategy, commits)
    all_strategy_groups.extend(temporal_groups)
    
    semantic_groups = analyze_individual_strategy("Semantic", semantic_strategy, commits)
    all_strategy_groups.extend(semantic_groups)
    
    dependency_groups = analyze_individual_strategy("Dependency", dependency_strategy, commits)
    all_strategy_groups.extend(dependency_groups)
    
    # Detailed analysis
    analyze_file_overlap_details(commits, config)
    analyze_semantic_similarity(commits, config)
    
    # Deduplication analysis
    final_groups = analyze_deduplication_process(all_strategy_groups, engine)
    
    # Configuration impact
    analyze_configuration_impact(commits)
    
    # Run the full engine and compare
    print_separator("FULL ENGINE RESULTS")
    engine_groups, warnings = engine.group_commits(commits)
    
    print(f"Final groups from engine: {len(engine_groups)}")
    print(f"Warnings: {warnings}")
    
    for i, group in enumerate(engine_groups):
        print(f"\n  Final Group {i+1}:")
        print(f"    Commits: {[c.short_hash for c in group.commits]}")
        print(f"    Rationale: {group.rationale}")
        print(f"    Message: {group.suggested_message}")
    
    # Quality analysis
    quality_metrics = engine.analyze_grouping_quality(engine_groups)
    print(f"\nQuality metrics:")
    for metric, value in quality_metrics.items():
        print(f"    {metric}: {value}")


def main():
    """Main entry point."""
    try:
        run_full_debug_analysis()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())