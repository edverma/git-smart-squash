"""Test automatic dependency resolution in the CLI."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.diff_parser import Hunk
from git_smart_squash.dependency_validator import DependencyValidator


class TestAutoDependencyResolution(unittest.TestCase):
    """Test automatic dependency resolution functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cli = GitSmartSquashCLI()
        self.cli.console = Mock()
        self.cli.config = Mock(
            hunks=Mock(max_hunks_per_prompt=100),
            ai=Mock(instructions=None)
        )
    
    def test_auto_fix_simple_dependency_violation(self):
        """Test automatic fixing of simple dependency violations."""
        # Create hunks with dependencies
        hunks = [
            Hunk(id="h1", file_path="file.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file.py", start_line=10, end_line=15, 
                 content="", context=""),
            Hunk(id="h3", file_path="other.py", start_line=1, end_line=5, 
                 content="", context=""),
        ]
        
        # Invalid commit plan (h1 depends on h2 but they're in different commits)
        invalid_plan = {
            "commits": [
                {"message": "First commit", "hunk_ids": ["h1", "h3"], "rationale": "Test"},
                {"message": "Second commit", "hunk_ids": ["h2"], "rationale": "Test"},
            ]
        }
        
        validator = DependencyValidator()
        fixed_plan = self.cli._auto_fix_dependencies(invalid_plan, hunks, validator)
        
        # Should fix the dependency issue
        self.assertIsNotNone(fixed_plan)
        
        # With the improved algorithm, it should reorder commits rather than merge
        # h2 should come before h1
        commits = fixed_plan["commits"]
        self.assertEqual(len(commits), 2)
        
        # Find which commit has h2 and which has h1
        h2_idx = None
        h1_idx = None
        for idx, commit in enumerate(commits):
            if "h2" in commit["hunk_ids"]:
                h2_idx = idx
            if "h1" in commit["hunk_ids"]:
                h1_idx = idx
        
        # h2 should come before h1
        self.assertIsNotNone(h1_idx)
        self.assertIsNotNone(h2_idx)
        self.assertLess(h2_idx, h1_idx)
    
    def test_merge_all_commits_fallback(self):
        """Test the merge all commits fallback."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h2", file_path="file2.py", start_line=1, end_line=5, 
                 content="", context=""),
        ]
        
        plan = {
            "commits": [
                {"message": "Feature A", "hunk_ids": ["h1"], "rationale": "Test A"},
                {"message": "Feature B", "hunk_ids": ["h2"], "rationale": "Test B"},
            ]
        }
        
        merged_plan = self.cli._merge_all_commits(plan, hunks)
        
        # Should have single commit
        self.assertEqual(len(merged_plan["commits"]), 1)
        
        # Should contain all hunks
        merged_commit = merged_plan["commits"][0]
        self.assertIn("h1", merged_commit["hunk_ids"])
        self.assertIn("h2", merged_commit["hunk_ids"])
        
        # Should mention consolidation in message
        self.assertIn("Consolidated", merged_commit["message"])
    
    @patch('git_smart_squash.cli.Progress')
    @patch('git_smart_squash.cli.subprocess.run')
    @patch.object(GitSmartSquashCLI, 'get_full_diff')
    @patch.object(GitSmartSquashCLI, 'analyze_with_ai')
    def test_auto_resolution_integration(self, mock_ai, mock_get_diff, mock_subprocess, mock_progress):
        """Test full integration with automatic resolution."""
        # Mock progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Mock git diff
        mock_get_diff.return_value = "diff --git a/file.py b/file.py\\n..."
        
        # Create hunks with dependencies
        hunks = [
            Hunk(id="h1", file_path="file.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        # Mock AI response with invalid plan
        mock_ai.return_value = {
            "commits": [
                {"message": "First", "hunk_ids": ["h1"], "rationale": "Test"},
                {"message": "Second", "hunk_ids": ["h2"], "rationale": "Test"},
            ]
        }
        
        with patch('git_smart_squash.cli.parse_diff', return_value=hunks):
            with patch.object(self.cli, 'display_commit_plan') as mock_display:
                with patch.object(self.cli, 'apply_commit_plan') as mock_apply:
                    # Run with auto-apply
                    args = Mock(
                        base="main",
                        ai_provider="test",
                        instructions=None,
                        auto_apply=True,
                        debug=False,
                        log_level=None,
                        verbose=False,
                        no_attribution=False
                    )
                    
                    self.cli.run_smart_squash(args)
                    
                    # Should show automatic fixing message
                    console_calls = [str(call) for call in self.cli.console.print.call_args_list]
                    self.assertTrue(any("Dependency violations detected" in call for call in console_calls))
                    self.assertTrue(any("Successfully reorganized" in call for call in console_calls))
                    
                    # Should have applied the fixed plan
                    mock_apply.assert_called_once()
                    applied_plan = mock_apply.call_args[0][0]
                    
                    # Should have fixed the commits by reordering
                    self.assertEqual(len(applied_plan["commits"]), 2)
                    
                    # Verify h2 comes before h1 in the fixed plan
                    h2_idx = None
                    h1_idx = None
                    for idx, commit in enumerate(applied_plan["commits"]):
                        if "h2" in commit["hunk_ids"]:
                            h2_idx = idx
                        if "h1" in commit["hunk_ids"]:
                            h1_idx = idx
                    
                    self.assertIsNotNone(h1_idx)
                    self.assertIsNotNone(h2_idx)
                    self.assertLess(h2_idx, h1_idx)


if __name__ == "__main__":
    unittest.main()