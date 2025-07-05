#!/usr/bin/env python3
"""
Test suite for backup/restore functionality.

This test suite validates the backup and restore capabilities including:
1. BackupManager creation and restoration
2. Integration with CLI apply_commit_plan
3. Automatic restoration on failure
4. Backup branch preservation
5. Repository integrity checks
"""

import unittest
import tempfile
import shutil
import subprocess
import os
import time
from unittest.mock import patch, MagicMock

# Import the modules we're testing
from git_smart_squash.strategies.backup_manager import BackupManager
from git_smart_squash.hunk_applicator import (
    check_repository_integrity, 
    get_backup_restoration_info,
    apply_hunks_with_fallback
)


class TestBackupManager(unittest.TestCase):
    """Test suite for BackupManager functionality."""
    
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
        
        self.backup_manager = BackupManager()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_backup_creation(self):
        """Test that backup branches are created correctly."""
        # Create backup
        backup_name = self.backup_manager.create_backup()
        
        # Verify backup branch exists
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup branch should exist")
        
        # Verify backup points to current HEAD
        head_commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        backup_commit = subprocess.run(
            ['git', 'rev-parse', backup_name],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        self.assertEqual(head_commit, backup_commit, "Backup should point to current HEAD")
    
    def test_backup_with_prefix(self):
        """Test backup creation with custom prefix."""
        backup_name = self.backup_manager.create_backup(prefix="custom-test")
        
        self.assertIn("custom-test-backup", backup_name)
        self.assertIn(str(int(time.time())), backup_name)
    
    def test_backup_restoration(self):
        """Test restoration from backup branch."""
        # Create initial state
        with open('test.txt', 'w') as f:
            f.write('modified content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Modified commit'], check=True)
        
        # Create backup
        backup_name = self.backup_manager.create_backup()
        
        # Make more changes
        with open('test.txt', 'w') as f:
            f.write('further changes\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Further changes'], check=True)
        
        # Restore from backup
        success = self.backup_manager.restore_from_backup(backup_name)
        self.assertTrue(success, "Backup restoration should succeed")
        
        # Verify restoration worked
        with open('test.txt', 'r') as f:
            content = f.read()
        self.assertEqual(content, 'modified content\n', "File should be restored to backup state")
    
    def test_backup_context_manager_success(self):
        """Test backup context manager preserves backup on success."""
        original_head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        backup_name = None
        with self.backup_manager.backup_context() as backup:
            backup_name = backup
            # Simulate successful operation
            with open('success.txt', 'w') as f:
                f.write('success\n')
            subprocess.run(['git', 'add', 'success.txt'], check=True)
            subprocess.run(['git', 'commit', '-m', 'Success'], check=True)
        
        # Verify backup still exists
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup should be preserved on success")
        
        # Verify backup points to original state
        backup_commit = subprocess.run(
            ['git', 'rev-parse', backup_name],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(original_head, backup_commit, "Backup should preserve original state")
    
    def test_backup_context_manager_failure(self):
        """Test backup context manager restores on failure."""
        original_head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        
        backup_name = None
        try:
            with self.backup_manager.backup_context() as backup:
                backup_name = backup
                # Make changes
                with open('failure.txt', 'w') as f:
                    f.write('failure\n')
                subprocess.run(['git', 'add', 'failure.txt'], check=True)
                subprocess.run(['git', 'commit', '-m', 'Before failure'], check=True)
                
                # Simulate failure
                raise Exception("Simulated failure")
        except Exception:
            pass  # Expected
        
        # Verify we're back to original state
        current_head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(original_head, current_head, "Should be restored to original state")
        
        # Verify backup still exists
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup should be preserved for debugging")
    
    def test_list_backups(self):
        """Test listing backup branches."""
        # Create multiple backups
        backup1 = self.backup_manager.create_backup(prefix="test1")
        backup2 = self.backup_manager.create_backup(prefix="test2")
        
        backups = self.backup_manager.list_backups()
        
        self.assertIn(backup1, backups, "First backup should be listed")
        self.assertIn(backup2, backups, "Second backup should be listed")
        self.assertGreaterEqual(len(backups), 2, "Should have at least 2 backups")


class TestRepositoryIntegrity(unittest.TestCase):
    """Test suite for repository integrity checking."""
    
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
            f.write('test content\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_repository_integrity_clean(self):
        """Test integrity check on clean repository."""
        result = check_repository_integrity()
        self.assertTrue(result, "Clean repository should pass integrity check")
    
    def test_backup_restoration_info(self):
        """Test gathering backup restoration information."""
        info = get_backup_restoration_info()
        
        # Verify required keys exist
        required_keys = ["current_branch", "head_commit", "staged_files", "working_dir_status"]
        for key in required_keys:
            self.assertIn(key, info, f"Info should contain {key}")
        
        # Verify values are reasonable
        self.assertEqual(info["current_branch"], "main", "Should be on main branch")
        self.assertEqual(info["staged_files"], "none", "Should have no staged files")
        self.assertEqual(info["working_dir_status"], "clean", "Should have clean working dir")
        self.assertEqual(len(info["head_commit"]), 8, "HEAD commit should be 8 characters")


class TestBackupIntegration(unittest.TestCase):
    """Test suite for backup integration with hunk application."""
    
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
        with open('test.py', 'w') as f:
            f.write('def test():\n    pass\n')
        subprocess.run(['git', 'add', 'test.py'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    @patch('git_smart_squash.hunk_applicator.apply_hunks')
    def test_apply_hunks_with_fallback_success(self, mock_apply_hunks):
        """Test successful hunk application with fallback."""
        mock_apply_hunks.return_value = True
        
        result = apply_hunks_with_fallback([], {}, "")
        
        self.assertTrue(result, "Should return True on success")
        mock_apply_hunks.assert_called_once()
    
    @patch('git_smart_squash.hunk_applicator.apply_hunks')
    def test_apply_hunks_with_fallback_failure(self, mock_apply_hunks):
        """Test failed hunk application with fallback."""
        mock_apply_hunks.return_value = False
        
        result = apply_hunks_with_fallback([], {}, "")
        
        self.assertFalse(result, "Should return False on failure")
        mock_apply_hunks.assert_called_once()
    
    @patch('git_smart_squash.hunk_applicator.apply_hunks')
    def test_apply_hunks_with_fallback_exception(self, mock_apply_hunks):
        """Test exception handling in hunk application."""
        mock_apply_hunks.side_effect = Exception("Test exception")
        
        result = apply_hunks_with_fallback([], {}, "")
        
        self.assertFalse(result, "Should return False on exception")
        mock_apply_hunks.assert_called_once()


class TestBackupPreservation(unittest.TestCase):
    """Test that backup branches are always preserved."""
    
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
            f.write('initial\n')
        subprocess.run(['git', 'add', 'test.txt'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], check=True)
        
        self.backup_manager = BackupManager()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_backup_preserved_on_success(self):
        """Test that backups are preserved even on successful operations."""
        backup_name = None
        
        # Simulate successful operation
        with self.backup_manager.backup_context() as backup:
            backup_name = backup
            # Make some changes
            with open('success.txt', 'w') as f:
                f.write('success\n')
            subprocess.run(['git', 'add', 'success.txt'], check=True)
            subprocess.run(['git', 'commit', '-m', 'Success'], check=True)
        
        # Verify backup still exists after successful context exit
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup should be preserved after success")
        
        # Verify backup is in created_backups list
        self.assertIn(backup_name, self.backup_manager.created_backups)
    
    def test_backup_preserved_on_failure(self):
        """Test that backups are preserved on failed operations."""
        backup_name = None
        
        try:
            with self.backup_manager.backup_context() as backup:
                backup_name = backup
                # Make some changes
                with open('failure.txt', 'w') as f:
                    f.write('failure\n')
                subprocess.run(['git', 'add', 'failure.txt'], check=True)
                subprocess.run(['git', 'commit', '-m', 'Before failure'], check=True)
                
                # Simulate failure
                raise Exception("Simulated failure")
        except Exception:
            pass  # Expected
        
        # Verify backup still exists after failed context exit
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup should be preserved after failure")
        
        # Verify backup is in created_backups list
        self.assertIn(backup_name, self.backup_manager.created_backups)
    
    def test_manual_cleanup_functionality(self):
        """Test that manual cleanup works when explicitly called."""
        backup_name = self.backup_manager.create_backup()
        
        # Verify backup exists
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, "Backup should exist before cleanup")
        
        # Manually clean up
        self.backup_manager.cleanup_backup(backup_name)
        
        # Verify backup is removed
        result = subprocess.run(
            ['git', 'rev-parse', '--verify', backup_name],
            capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0, "Backup should be removed after manual cleanup")


if __name__ == '__main__':
    unittest.main()