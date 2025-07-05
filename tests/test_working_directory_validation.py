#!/usr/bin/env python3
"""
Test suite for working directory validation functionality.

This test suite validates that:
1. Working directory cleanliness checks work correctly
2. Tool properly blocks operations when uncommitted changes exist
3. Helpful error messages are displayed for different scenarios
4. Clean working directory allows operations to proceed
"""

import unittest
import tempfile
import shutil
import subprocess
import os
from unittest.mock import patch, MagicMock
from io import StringIO

# Import the modules we're testing
from git_smart_squash.cli import GitSmartSquashCLI


class TestWorkingDirectoryValidation(unittest.TestCase):
    """Test suite for working directory validation."""
    
    def setUp(self):
        """Set up test environment with a temporary git repository."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repository
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        
        # Create initial commit
        with open('test.txt', 'w') as f:
            f.write('initial content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        self.cli = GitSmartSquashCLI()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_clean_working_directory(self):
        """Test detection of clean working directory."""
        status_info = self.cli._check_working_directory_clean()
        
        self.assertTrue(status_info['is_clean'], "Clean directory should be detected as clean")
        self.assertEqual(len(status_info['staged_files']), 0, "Should have no staged files")
        self.assertEqual(len(status_info['unstaged_files']), 0, "Should have no unstaged files")
        self.assertEqual(len(status_info['untracked_files']), 0, "Should have no untracked files")
        self.assertEqual(status_info['message'], "Working directory is clean")
    
    def test_staged_files_detection(self):
        """Test detection of staged files."""
        # Create and stage a file
        with open('staged.txt', 'w') as f:
            f.write('staged content\n')
        subprocess.run(['git', 'add', 'staged.txt'], check=True)
        
        status_info = self.cli._check_working_directory_clean()
        
        self.assertFalse(status_info['is_clean'], "Directory with staged files should not be clean")
        self.assertIn('staged.txt', status_info['staged_files'], "Staged file should be detected")
        self.assertEqual(len(status_info['unstaged_files']), 0, "Should have no unstaged files")
        self.assertEqual(len(status_info['untracked_files']), 0, "Should have no untracked files")
        self.assertIn("staged file(s)", status_info['message'])
    
    def test_unstaged_changes_detection(self):
        """Test detection of unstaged changes."""
        # Modify existing file
        with open('test.txt', 'w') as f:
            f.write('modified content\n')
        
        status_info = self.cli._check_working_directory_clean()
        
        self.assertFalse(status_info['is_clean'], "Directory with unstaged changes should not be clean")
        self.assertEqual(len(status_info['staged_files']), 0, "Should have no staged files")
        self.assertIn('test.txt', status_info['unstaged_files'], "Modified file should be detected")
        self.assertEqual(len(status_info['untracked_files']), 0, "Should have no untracked files")
        self.assertIn("unstaged change(s)", status_info['message'])
    
    def test_untracked_files_detection(self):
        """Test detection of untracked files."""
        # Create untracked file
        with open('untracked.txt', 'w') as f:
            f.write('untracked content\n')
        
        status_info = self.cli._check_working_directory_clean()
        
        self.assertFalse(status_info['is_clean'], "Directory with untracked files should not be clean")
        self.assertEqual(len(status_info['staged_files']), 0, "Should have no staged files")
        self.assertEqual(len(status_info['unstaged_files']), 0, "Should have no unstaged files")
        self.assertIn('untracked.txt', status_info['untracked_files'], "Untracked file should be detected")
        self.assertIn("untracked file(s)", status_info['message'])
    
    def test_mixed_changes_detection(self):
        """Test detection of mixed types of changes."""
        # Create staged file
        with open('staged.txt', 'w') as f:
            f.write('staged content\n')
        subprocess.run(['git', 'add', 'staged.txt'], check=True)
        
        # Modify existing file (unstaged)
        with open('test.txt', 'w') as f:
            f.write('modified content\n')
        
        # Create untracked file
        with open('untracked.txt', 'w') as f:
            f.write('untracked content\n')
        
        status_info = self.cli._check_working_directory_clean()
        
        self.assertFalse(status_info['is_clean'], "Directory with mixed changes should not be clean")
        self.assertIn('staged.txt', status_info['staged_files'], "Staged file should be detected")
        self.assertIn('test.txt', status_info['unstaged_files'], "Modified file should be detected")
        self.assertIn('untracked.txt', status_info['untracked_files'], "Untracked file should be detected")
        
        # Check message contains all types
        message = status_info['message']
        self.assertIn("staged file(s)", message)
        self.assertIn("unstaged change(s)", message)
        self.assertIn("untracked file(s)", message)


class TestWorkingDirectoryIntegration(unittest.TestCase):
    """Test integration of working directory validation with CLI."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repository
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        
        # Create initial commit on main branch
        with open('test.txt', 'w') as f:
            f.write('initial content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        # Create feature branch with changes
        subprocess.run(['git', 'checkout', '-b', 'feature'], check=True)
        with open('test.txt', 'w') as f:
            f.write('feature content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Feature commit'], check=True)
        
        self.cli = GitSmartSquashCLI()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    @patch('git_smart_squash.cli.GitSmartSquashCLI.get_user_confirmation')
    @patch('git_smart_squash.cli.GitSmartSquashCLI.analyze_with_ai')
    def test_clean_directory_allows_operation(self, mock_analyze, mock_confirm):
        """Test that clean working directory allows operation to proceed."""
        # Mock AI response
        mock_analyze.return_value = {
            "commits": [
                {
                    "message": "feature: test change",
                    "hunk_ids": ["test.txt:1-1"],
                    "rationale": "Test commit"
                }
            ]
        }
        mock_confirm.return_value = False  # Don't actually apply
        
        # Create mock args
        args = MagicMock()
        args.base = 'main'
        args.auto_apply = False
        args.instructions = None
        args.no_attribution = False
        
        # This should not raise an exception and should proceed to showing plan
        try:
            self.cli.run_smart_squash(args)
            # If we get here, the working directory check passed
            operation_started = True
        except SystemExit:
            operation_started = False
        
        # Verify the AI was called (meaning we got past working directory check)
        self.assertTrue(mock_analyze.called, "AI analysis should be called when directory is clean")
    
    def test_staged_changes_blocks_operation(self):
        """Test that staged changes block operation."""
        # Create staged changes
        with open('staged.txt', 'w') as f:
            f.write('staged content\n')
        subprocess.run(['git', 'add', 'staged.txt'], check=True)
        
        # Create mock args
        args = MagicMock()
        args.base = 'main'
        args.auto_apply = False
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            # Run the operation
            self.cli.run_smart_squash(args)
            
            # Check that error message was printed
            print_calls = [call for call in mock_console.print.call_args_list]
            error_messages = [str(call) for call in print_calls if 'Cannot proceed' in str(call)]
            self.assertTrue(len(error_messages) > 0, "Should display error message for staged changes")
    
    def test_unstaged_changes_blocks_operation(self):
        """Test that unstaged changes block operation."""
        # Create unstaged changes
        with open('test.txt', 'w') as f:
            f.write('modified content\n')
        
        # Create mock args
        args = MagicMock()
        args.base = 'main'
        args.auto_apply = False
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            # Run the operation
            self.cli.run_smart_squash(args)
            
            # Check that error message was printed
            print_calls = [call for call in mock_console.print.call_args_list]
            error_messages = [str(call) for call in print_calls if 'Cannot proceed' in str(call)]
            self.assertTrue(len(error_messages) > 0, "Should display error message for unstaged changes")
    
    def test_untracked_files_blocks_operation(self):
        """Test that untracked files block operation."""
        # Create untracked file
        with open('untracked.txt', 'w') as f:
            f.write('untracked content\n')
        
        # Create mock args
        args = MagicMock()
        args.base = 'main'
        args.auto_apply = False
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            # Run the operation
            self.cli.run_smart_squash(args)
            
            # Check that error message was printed
            print_calls = [call for call in mock_console.print.call_args_list]
            error_messages = [str(call) for call in print_calls if 'Cannot proceed' in str(call)]
            self.assertTrue(len(error_messages) > 0, "Should display error message for untracked files")


class TestWorkingDirectoryHelpMessages(unittest.TestCase):
    """Test help messages for different working directory states."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize git repository
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        
        # Create initial commit
        with open('test.txt', 'w') as f:
            f.write('initial content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        self.cli = GitSmartSquashCLI()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_staged_files_help_message(self):
        """Test help message for staged files."""
        # Create staged file
        with open('staged.txt', 'w') as f:
            f.write('staged content\n')
        subprocess.run(['git', 'add', 'staged.txt'], check=True)
        
        status_info = self.cli._check_working_directory_clean()
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            self.cli._display_working_directory_help(status_info)
            
            # Check that appropriate help was displayed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            help_text = ' '.join(print_calls)
            
            self.assertIn('staged.txt', help_text, "Should mention the staged file")
            self.assertIn('git commit', help_text, "Should suggest committing")
            self.assertIn('git reset HEAD', help_text, "Should suggest unstaging")
    
    def test_unstaged_changes_help_message(self):
        """Test help message for unstaged changes."""
        # Modify existing file
        with open('test.txt', 'w') as f:
            f.write('modified content\n')
        
        status_info = self.cli._check_working_directory_clean()
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            self.cli._display_working_directory_help(status_info)
            
            # Check that appropriate help was displayed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            help_text = ' '.join(print_calls)
            
            self.assertIn('test.txt', help_text, "Should mention the modified file")
            self.assertIn('git add', help_text, "Should suggest staging and committing")
            self.assertIn('git stash', help_text, "Should suggest stashing")
            self.assertIn('git checkout', help_text, "Should suggest discarding")
    
    def test_untracked_files_help_message(self):
        """Test help message for untracked files."""
        # Create untracked file
        with open('untracked.txt', 'w') as f:
            f.write('untracked content\n')
        
        status_info = self.cli._check_working_directory_clean()
        
        # Capture console output
        with patch('git_smart_squash.cli.Console') as mock_console_class:
            mock_console = MagicMock()
            mock_console_class.return_value = mock_console
            self.cli.console = mock_console
            
            self.cli._display_working_directory_help(status_info)
            
            # Check that appropriate help was displayed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            help_text = ' '.join(print_calls)
            
            self.assertIn('untracked.txt', help_text, "Should mention the untracked file")
            self.assertIn('git add', help_text, "Should suggest adding and committing")
            self.assertIn('.gitignore', help_text, "Should suggest ignoring")


if __name__ == '__main__':
    unittest.main()