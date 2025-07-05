"""Backup management for git operations."""

import time
import subprocess
from typing import Optional, List
from contextlib import contextmanager

from ..logger import get_logger

logger = get_logger()


class BackupManager:
    """Manages backup branches and recovery using subprocess calls."""
    
    def __init__(self):
        self.backup_branch: Optional[str] = None
        self.created_backups: List[str] = []
        
    def create_backup(self, prefix: str = None) -> str:
        """Create backup branch before operations.
        
        Args:
            prefix: Optional prefix for the backup branch name
            
        Returns:
            Name of the created backup branch
            
        Raises:
            Exception: If backup creation fails
        """
        try:
            # Verify working directory is clean before creating backup
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, check=True
            )
            
            if status_result.stdout.strip():
                raise Exception("Working directory is not clean - backup would not preserve uncommitted changes")
            
            # Get current branch name
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, check=True
            )
            current_branch = result.stdout.strip()
            
            timestamp = int(time.time())
            
            if prefix:
                self.backup_branch = f"{prefix}-backup-{timestamp}"
            else:
                self.backup_branch = f"{current_branch}-backup-{timestamp}"
                
            # Create backup branch pointing to current HEAD
            subprocess.run(
                ['git', 'branch', self.backup_branch],
                check=True, capture_output=True
            )
            
            self.created_backups.append(self.backup_branch)
            
            logger.info(f"Created backup branch: {self.backup_branch}")
            logger.debug(f"Backup branch {self.backup_branch} points to current HEAD and preserves your work")
            return self.backup_branch
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create backup branch: {e.stderr if e.stderr else str(e)}")
            raise Exception(f"Failed to create backup branch: {e.stderr if e.stderr else str(e)}")
        
    def restore_from_backup(self, backup_name: Optional[str] = None) -> bool:
        """Restore from backup branch using hard reset.
        
        Args:
            backup_name: Specific backup to restore from. If None, uses last backup.
            
        Returns:
            True if restoration successful, False otherwise
        """
        backup_to_use = backup_name or self.backup_branch
        
        if not backup_to_use:
            logger.error("No backup branch available for restoration")
            return False
            
        try:
            # Verify backup branch exists
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', backup_to_use],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Backup branch {backup_to_use} does not exist")
                return False
            
            # Hard reset current branch to backup state
            subprocess.run(
                ['git', 'reset', '--hard', backup_to_use],
                check=True, capture_output=True
            )
            
            logger.info(f"Successfully restored from backup branch: {backup_to_use}")
            logger.debug(f"Repository state has been reset to the backup point, undoing all changes since backup creation")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restore from backup: {e.stderr if e.stderr else str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during restore: {str(e)}")
            return False
        
    def cleanup_backup(self, backup_name: Optional[str] = None) -> None:
        """Remove backup branch manually (not used in auto-preserve mode).
        
        NOTE: This method is kept for manual cleanup but is not used in
        the main workflow since backup branches are always preserved.
        
        Args:
            backup_name: Specific backup to remove. If None, removes last backup.
        """
        backup_to_clean = backup_name or self.backup_branch
        
        if not backup_to_clean:
            return
            
        try:
            # Check if branch exists
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', backup_to_clean],
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                # Delete the branch
                subprocess.run(
                    ['git', 'branch', '-D', backup_to_clean],
                    check=True, capture_output=True
                )
                logger.info(f"Manually deleted backup branch: {backup_to_clean}")
                
                if backup_to_clean in self.created_backups:
                    self.created_backups.remove(backup_to_clean)
                    
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to delete backup branch {backup_to_clean}: {e.stderr if e.stderr else str(e)}")
        except Exception as e:
            logger.warning(f"Unexpected error deleting backup branch {backup_to_clean}: {str(e)}")
            
    def cleanup_all_backups(self) -> None:
        """Remove all backup branches created by this manager (manual operation only).
        
        NOTE: This method is kept for manual cleanup but is not used in
        the main workflow since backup branches are always preserved.
        """
        for backup_name in self.created_backups[:]:
            self.cleanup_backup(backup_name)
            
    def list_backups(self) -> List[str]:
        """List all backup branches in the repository."""
        backup_branches = []
        
        try:
            # Get list of all branches
            result = subprocess.run(
                ['git', 'branch', '--list'],
                capture_output=True, text=True, check=True
            )
            
            # Parse branch names and filter for backup branches
            for line in result.stdout.split('\n'):
                branch_name = line.strip().lstrip('* ').strip()
                if branch_name and 'backup' in branch_name:
                    backup_branches.append(branch_name)
                    
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to list branches: {e.stderr if e.stderr else str(e)}")
                
        return backup_branches
    
    @contextmanager
    def backup_context(self, prefix: str = None, auto_restore_on_failure: bool = True):
        """Context manager for backup operations with automatic restoration on failure.
        
        Args:
            prefix: Optional prefix for backup branch name
            auto_restore_on_failure: If True, automatically restores from backup on exception
            
        Usage:
            with backup_manager.backup_context():
                # Perform operations
                # Backup automatically created and ALWAYS preserved
                # On failure, automatically restores to backup state
        """
        backup_name = self.create_backup(prefix)
        
        try:
            yield backup_name
            
            # Success - backup is always preserved
            logger.info(f"Operation completed successfully. Backup branch {backup_name} preserved for safety.")
            logger.debug(f"You can restore this backup later with: git reset --hard {backup_name}")
            logger.debug(f"You can delete this backup when no longer needed with: git branch -D {backup_name}")
                
        except Exception as e:
            # Error - restore from backup if requested, then preserve backup
            logger.error(f"Error during backup context: {str(e)}")
            
            if auto_restore_on_failure:
                logger.info(f"Attempting to restore from backup branch: {backup_name}")
                if self.restore_from_backup(backup_name):
                    logger.info(f"Successfully restored from backup. Repository state recovered.")
                else:
                    logger.error(f"Failed to restore from backup. Manual intervention may be required.")
            
            logger.info(f"Backup branch {backup_name} preserved for investigation")
            raise
            
    def __enter__(self):
        """Context manager entry."""
        self.create_backup()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - backup is always preserved."""
        if exc_type is None:
            # No exception - backup still preserved
            logger.info(f"Operation completed successfully. Backup branch {self.backup_branch} preserved for safety.")
        else:
            # Exception occurred - backup preserved for debugging
            logger.info(f"Backup branch {self.backup_branch} preserved for investigation due to error")