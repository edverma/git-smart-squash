"""Test the improved auto-fix dependency resolution algorithm."""

import unittest
from unittest.mock import Mock
from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.diff_parser import Hunk
from git_smart_squash.dependency_validator import DependencyValidator


class TestImprovedAutoFix(unittest.TestCase):
    """Test the improved dependency resolution with graph analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cli = GitSmartSquashCLI()
        self.cli.console = Mock()
        self.cli.config = Mock(
            hunks=Mock(max_hunks_per_prompt=100),
            ai=Mock(instructions=None)
        )
        self.cli.logger = Mock()
    
    def test_build_commit_dependency_graph(self):
        """Test building the commit-level dependency graph."""
        hunks = [
            Hunk(id="h1", file_path="a.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2", "h3"}),
            Hunk(id="h2", file_path="b.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h3", file_path="c.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h4"}),
            Hunk(id="h4", file_path="d.py", start_line=1, end_line=5, 
                 content="", context=""),
        ]
        
        commits = [
            {"message": "Commit 1", "hunk_ids": ["h1"]},  # Depends on commits 1 and 2
            {"message": "Commit 2", "hunk_ids": ["h2", "h3"]},  # h3 depends on commit 3
            {"message": "Commit 3", "hunk_ids": ["h4"]},
        ]
        
        hunk_map = {h.id: h for h in hunks}
        graph = self.cli._build_commit_dependency_graph(commits, hunk_map)
        
        # Commit 0 depends on commits 1 (for h2) and 2 (for h3)
        self.assertEqual(graph[0], {1})
        # Commit 1 has h3 which depends on commit 2 (for h4)
        self.assertEqual(graph[1], {2})
        # Commit 2 has no dependencies
        self.assertEqual(graph[2], set())
    
    def test_find_strongly_connected_components_no_cycles(self):
        """Test SCC finding with no cycles."""
        # Linear dependency graph: 0 -> 1 -> 2
        graph = {
            0: {1},
            1: {2},
            2: set()
        }
        
        sccs = self.cli._find_strongly_connected_components(graph)
        
        # Each commit should be in its own SCC
        self.assertEqual(len(sccs), 3)
        for scc in sccs:
            self.assertEqual(len(scc), 1)
    
    def test_find_strongly_connected_components_with_cycle(self):
        """Test SCC finding with circular dependencies."""
        # Circular dependency: 0 -> 1 -> 2 -> 0
        graph = {
            0: {1},
            1: {2},
            2: {0}
        }
        
        sccs = self.cli._find_strongly_connected_components(graph)
        
        # All three commits should be in one SCC
        self.assertEqual(len(sccs), 1)
        self.assertEqual(sorted(sccs[0]), [0, 1, 2])
    
    def test_find_strongly_connected_components_partial_cycle(self):
        """Test SCC with partial cycle."""
        # Graph: 0 -> 1 -> 2 -> 1, and 3 is independent
        graph = {
            0: {1},
            1: {2},
            2: {1},
            3: set()
        }
        
        sccs = self.cli._find_strongly_connected_components(graph)
        
        # Should have 3 SCCs: [0], [1,2], [3]
        self.assertEqual(len(sccs), 3)
        scc_sizes = sorted([len(scc) for scc in sccs])
        self.assertEqual(scc_sizes, [1, 1, 2])
    
    def test_merge_sccs_preserves_single_commits(self):
        """Test that single-commit SCCs are preserved."""
        commits = [
            {"message": "Commit 1", "hunk_ids": ["h1"], "rationale": "Test 1"},
            {"message": "Commit 2", "hunk_ids": ["h2"], "rationale": "Test 2"},
            {"message": "Commit 3", "hunk_ids": ["h3"], "rationale": "Test 3"},
        ]
        
        # Each commit is its own SCC
        sccs = [[0], [1], [2]]
        
        merged = self.cli._merge_sccs(commits, sccs)
        
        # Should preserve all original commits
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["message"], "Commit 1")
        self.assertEqual(merged[1]["message"], "Commit 2")
        self.assertEqual(merged[2]["message"], "Commit 3")
    
    def test_merge_sccs_merges_circular_dependencies(self):
        """Test merging commits with circular dependencies."""
        commits = [
            {"message": "Feature A", "hunk_ids": ["h1"], "rationale": "Part A"},
            {"message": "Feature B", "hunk_ids": ["h2"], "rationale": "Part B"},
            {"message": "Feature C", "hunk_ids": ["h3"], "rationale": "Part C"},
        ]
        
        # Commits 0 and 1 are in a cycle, 2 is separate
        sccs = [[2], [0, 1]]
        
        merged = self.cli._merge_sccs(commits, sccs)
        
        # Should have 2 commits
        self.assertEqual(len(merged), 2)
        
        # Find the merged commit
        merged_commit = None
        for commit in merged:
            if len(commit["hunk_ids"]) > 1:
                merged_commit = commit
                break
        
        self.assertIsNotNone(merged_commit)
        self.assertIn("h1", merged_commit["hunk_ids"])
        self.assertIn("h2", merged_commit["hunk_ids"])
        self.assertIn("circular dependencies", merged_commit["rationale"])
    
    def test_topological_sort_linear_dependencies(self):
        """Test topological sorting with linear dependencies."""
        hunks = [
            Hunk(id="h1", file_path="a.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="b.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h3"}),
            Hunk(id="h3", file_path="c.py", start_line=1, end_line=5, 
                 content="", context=""),
        ]
        
        # Commits in wrong order
        commits = [
            {"message": "Third", "hunk_ids": ["h1"]},  # Depends on h2
            {"message": "First", "hunk_ids": ["h3"]},  # No dependencies
            {"message": "Second", "hunk_ids": ["h2"]},  # Depends on h3
        ]
        
        hunk_map = {h.id: h for h in hunks}
        sorted_commits = self.cli._topological_sort_commits(commits, hunk_map)
        
        self.assertIsNotNone(sorted_commits)
        self.assertEqual(len(sorted_commits), 3)
        
        # First commit should have h3 (no dependencies)
        self.assertIn("h3", sorted_commits[0]["hunk_ids"])
        # Second should have h2 (depends on h3)
        self.assertIn("h2", sorted_commits[1]["hunk_ids"])
        # Third should have h1 (depends on h2)
        self.assertIn("h1", sorted_commits[2]["hunk_ids"])
    
    def test_complex_dependency_resolution(self):
        """Test the full algorithm with complex dependencies."""
        # Create a complex scenario with partial circular dependencies
        hunks = [
            # Group 1: Circular dependency between h1 and h2
            Hunk(id="h1", file_path="a.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="a.py", start_line=10, end_line=15, 
                 content="", context="", dependencies={"h1"}),
            
            # Group 2: Linear dependency h3 -> h4
            Hunk(id="h3", file_path="b.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h4"}),
            Hunk(id="h4", file_path="b.py", start_line=10, end_line=15, 
                 content="", context=""),
            
            # Independent
            Hunk(id="h5", file_path="c.py", start_line=1, end_line=5, 
                 content="", context=""),
        ]
        
        invalid_plan = {
            "commits": [
                {"message": "Commit 1", "hunk_ids": ["h1"], "rationale": "Has h1"},
                {"message": "Commit 2", "hunk_ids": ["h2"], "rationale": "Has h2"},
                {"message": "Commit 3", "hunk_ids": ["h3"], "rationale": "Has h3"},
                {"message": "Commit 4", "hunk_ids": ["h4"], "rationale": "Has h4"},
                {"message": "Commit 5", "hunk_ids": ["h5"], "rationale": "Has h5"},
            ]
        }
        
        validator = DependencyValidator()
        fixed_plan = self.cli._auto_fix_dependencies(invalid_plan, hunks, validator)
        
        self.assertIsNotNone(fixed_plan)
        commits = fixed_plan["commits"]
        
        # Should have 4 commits (h1 and h2 merged due to circular dependency)
        self.assertEqual(len(commits), 4)
        
        # Verify the merged commit contains both h1 and h2
        merged_commit = None
        for commit in commits:
            if "h1" in commit["hunk_ids"] and "h2" in commit["hunk_ids"]:
                merged_commit = commit
                break
        
        self.assertIsNotNone(merged_commit)
        
        # Verify h4 comes before h3 in the final order
        h3_idx = h4_idx = None
        for idx, commit in enumerate(commits):
            if "h3" in commit["hunk_ids"]:
                h3_idx = idx
            if "h4" in commit["hunk_ids"]:
                h4_idx = idx
        
        self.assertIsNotNone(h3_idx)
        self.assertIsNotNone(h4_idx)
        self.assertLess(h4_idx, h3_idx)  # h4 should come before h3


if __name__ == "__main__":
    unittest.main()