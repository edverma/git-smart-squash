"""Integration test for dependency validation in CLI."""

import unittest
from unittest.mock import Mock, patch, MagicMock, ANY
from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.diff_parser import Hunk
import json


class TestDependencyValidationIntegration(unittest.TestCase):
    """Test dependency validation integration in CLI."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cli = GitSmartSquashCLI()
        # Mock the console to capture output
        self.cli.console = Mock()
        # Mock config
        self.cli.config = Mock(
            hunks=Mock(max_hunks_per_prompt=100),
            ai=Mock(instructions=None)
        )
        
    @patch('git_smart_squash.cli.Progress')
    @patch('git_smart_squash.cli.subprocess.run')
    @patch.object(GitSmartSquashCLI, 'get_full_diff')
    @patch.object(GitSmartSquashCLI, 'analyze_with_ai')
    def test_validation_shows_dependencies_as_informational(self, mock_ai, mock_get_diff, mock_subprocess, mock_progress):
        """Test that validation shows dependencies as informational and continues with original plan."""
        # Mock git diff output
        mock_get_diff.return_value = "diff --git a/file.py b/file.py\n@@ -1,5 +1,5 @@\n-old\n+new"
        
        # Create hunks with dependencies
        hunks = [
            Hunk(id="h1", file_path="file.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        # Mock AI response with invalid commit plan (h1 depends on h2 but h2 is in later commit)
        mock_ai.return_value = {
            "commits": [
                {"message": "First commit", "hunk_ids": ["h1"], "rationale": "Test rationale"},
                {"message": "Second commit", "hunk_ids": ["h2"], "rationale": "Test rationale"},
            ]
        }
        
        # Mock progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Patch parse_diff to return our test hunks
        with patch('git_smart_squash.cli.parse_diff', return_value=hunks):
            # Mock user confirmation
            with patch.object(self.cli, 'get_user_confirmation', return_value=True):
                with patch.object(self.cli, 'apply_commit_plan'):
                    # Run CLI with mocked args
                    args = Mock(
                        base="main",
                        ai_provider="test",
                        instructions=None,
                        auto_apply=False,
                        debug=False,
                        log_level=None,
                        verbose=False,
                        no_attribution=False
                    )
                    
                    # Run normally - should not raise SystemExit
                    self.cli.run_smart_squash(args)
            
            # Verify dependency notification was shown
            dep_calls = [call for call in self.cli.console.print.call_args_list 
                          if "Dependency relationships detected" in str(call)]
            self.assertTrue(len(dep_calls) > 0, "Expected dependency notification")
            
            # Verify dependency informational message was shown
            dep_info_calls = [call for call in self.cli.console.print.call_args_list 
                          if "Dependencies are informational" in str(call)]
            self.assertTrue(len(dep_info_calls) > 0, "Expected dependency informational message")
            
            # Should not have error messages
            error_calls = [call for call in self.cli.console.print.call_args_list 
                          if "Error:" in str(call)]
            self.assertEqual(len(error_calls), 0, "Should not show error messages")
    
    @patch('git_smart_squash.cli.Progress')
    @patch('git_smart_squash.cli.subprocess.run')
    @patch.object(GitSmartSquashCLI, 'get_full_diff')
    @patch.object(GitSmartSquashCLI, 'analyze_with_ai')
    def test_validation_allows_valid_plan(self, mock_ai, mock_get_diff, mock_subprocess, mock_progress):
        """Test that validation allows execution when plan is valid."""
        # Mock git diff output
        mock_get_diff.return_value = "diff --git a/file.py b/file.py\n@@ -1,5 +1,5 @@\n-old\n+new"
        
        # Create hunks with dependencies
        hunks = [
            Hunk(id="h1", file_path="file.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h2", file_path="file.py", start_line=10, end_line=15, 
                 content="", context="", dependencies={"h1"}),
        ]
        
        # Mock AI response with valid commit plan (h2 depends on h1, h1 comes first)
        mock_ai.return_value = {
            "commits": [
                {"message": "First commit", "hunk_ids": ["h1"]},
                {"message": "Second commit", "hunk_ids": ["h2"]},
            ]
        }
        
        # Mock progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # Patch parse_diff to return our test hunks
        with patch('git_smart_squash.cli.parse_diff', return_value=hunks):
            with patch.object(self.cli, 'display_commit_plan') as mock_display:
                with patch.object(self.cli, 'get_user_confirmation', return_value=False):
                    # Run CLI with mocked args
                    args = Mock(
                        base="main",
                        ai_provider="test",
                        instructions=None,
                        auto_apply=False,
                        debug=False,
                        log_level=None,
                        verbose=False,
                        no_attribution=False
                    )
                    
                    # Run should proceed normally until user confirmation
                    # The method will exit normally after user declines
                    try:
                        self.cli.run_smart_squash(args)
                    except SystemExit:
                        # This is expected since we're in the exception handler
                        pass
                    
                    # Verify no error message was printed
                    error_calls = [call for call in self.cli.console.print.call_args_list 
                                  if "Error: Commit plan violates dependencies" in str(call)]
                    self.assertEqual(len(error_calls), 0, "Should not have validation errors")
                    
                    # Verify display_commit_plan was called
                    mock_display.assert_called_once()
                    
                    # Verify we got to the confirmation stage
                    # (We're not mocking get_user_confirmation, so it will return False and exit)


if __name__ == "__main__":
    unittest.main()