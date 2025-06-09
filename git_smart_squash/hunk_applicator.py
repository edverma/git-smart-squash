"""
Hunk applicator module for applying specific hunks to the git staging area.
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional
from .diff_parser import Hunk, create_hunk_patch, validate_hunk_combination


class HunkApplicatorError(Exception):
    """Custom exception for hunk application errors."""
    pass


def apply_hunks(hunk_ids: List[str], hunks_by_id: Dict[str, Hunk], base_diff: str) -> bool:
    """
    Apply specific hunks to the git staging area.
    
    Args:
        hunk_ids: List of hunk IDs to apply
        hunks_by_id: Dictionary mapping hunk IDs to Hunk objects
        base_diff: Original full diff output
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        HunkApplicatorError: If hunk application fails
    """
    if not hunk_ids:
        return True
    
    # Get the hunks to apply
    hunks_to_apply = []
    for hunk_id in hunk_ids:
        if hunk_id not in hunks_by_id:
            raise HunkApplicatorError(f"Hunk ID not found: {hunk_id}")
        hunks_to_apply.append(hunks_by_id[hunk_id])
    
    # Validate that hunks can be applied together
    is_valid, error_msg = validate_hunk_combination(hunks_to_apply)
    if not is_valid:
        raise HunkApplicatorError(f"Invalid hunk combination: {error_msg}")
    
    # Create patch for selected hunks
    patch_content = create_hunk_patch(hunks_to_apply, base_diff)
    if not patch_content.strip():
        return True  # Nothing to apply
    
    # Apply the patch
    return _apply_patch_to_staging(patch_content)


def _apply_patch_to_staging(patch_content: str) -> bool:
    """
    Apply a patch to the git staging area using git apply --cached.
    
    Args:
        patch_content: The patch content to apply
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create a temporary file for the patch
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
            patch_file.write(patch_content)
            patch_file_path = patch_file.name
        
        try:
            # Apply the patch to the staging area
            result = subprocess.run(
                ['git', 'apply', '--cached', '--whitespace=nowarn', patch_file_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"Git apply failed: {result.stderr}")
                return False
            
            return True
            
        finally:
            # Clean up the temporary file
            try:
                os.unlink(patch_file_path)
            except OSError:
                pass
                
    except Exception as e:
        print(f"Error applying patch: {e}")
        return False


def apply_hunks_with_fallback(hunk_ids: List[str], hunks_by_id: Dict[str, Hunk], base_diff: str) -> bool:
    """
    Apply hunks with fallback to file-based staging if hunk application fails.
    
    Args:
        hunk_ids: List of hunk IDs to apply
        hunks_by_id: Dictionary mapping hunk IDs to Hunk objects
        base_diff: Original full diff output
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # First try hunk-based application
        return apply_hunks(hunk_ids, hunks_by_id, base_diff)
    except HunkApplicatorError:
        # Fallback to file-based staging
        print("Hunk application failed, falling back to file-based staging...")
        return _apply_files_fallback(hunk_ids, hunks_by_id)


def _apply_files_fallback(hunk_ids: List[str], hunks_by_id: Dict[str, Hunk]) -> bool:
    """
    Fallback method: stage entire files that contain the specified hunks.
    
    Args:
        hunk_ids: List of hunk IDs
        hunks_by_id: Dictionary mapping hunk IDs to Hunk objects
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get unique file paths from the hunks
        file_paths = set()
        for hunk_id in hunk_ids:
            if hunk_id in hunks_by_id:
                file_paths.add(hunks_by_id[hunk_id].file_path)
        
        if not file_paths:
            return True
        
        # Stage the files
        for file_path in file_paths:
            result = subprocess.run(
                ['git', 'add', file_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"Failed to stage file {file_path}: {result.stderr}")
                return False
        
        return True
        
    except Exception as e:
        print(f"Error in file fallback: {e}")
        return False


def reset_staging_area():
    """Reset the staging area to match HEAD."""
    try:
        result = subprocess.run(
            ['git', 'reset', 'HEAD'],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def create_patch_file_for_hunks(hunks: List[Hunk], base_diff: str, output_path: str) -> bool:
    """
    Create a patch file containing only the specified hunks.
    
    Args:
        hunks: List of hunks to include
        base_diff: Original full diff output
        output_path: Path where to save the patch file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        patch_content = create_hunk_patch(hunks, base_diff)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(patch_content)
        
        return True
        
    except Exception as e:
        print(f"Error creating patch file: {e}")
        return False


def preview_hunk_application(hunk_ids: List[str], hunks_by_id: Dict[str, Hunk]) -> str:
    """
    Generate a preview of what would be applied when staging these hunks.
    
    Args:
        hunk_ids: List of hunk IDs to preview
        hunks_by_id: Dictionary mapping hunk IDs to Hunk objects
        
    Returns:
        String description of what would be applied
    """
    if not hunk_ids:
        return "No hunks selected."
    
    # Group hunks by file
    files_affected = {}
    for hunk_id in hunk_ids:
        if hunk_id in hunks_by_id:
            hunk = hunks_by_id[hunk_id]
            if hunk.file_path not in files_affected:
                files_affected[hunk.file_path] = []
            files_affected[hunk.file_path].append(hunk)
    
    # Generate preview
    preview_lines = []
    for file_path, hunks in files_affected.items():
        preview_lines.append(f"File: {file_path}")
        for hunk in sorted(hunks, key=lambda h: h.start_line):
            line_range = f"lines {hunk.start_line}-{hunk.end_line}"
            preview_lines.append(f"  - {hunk.id} ({line_range})")
        preview_lines.append("")
    
    return "\n".join(preview_lines)


def get_staging_status() -> Dict[str, List[str]]:
    """
    Get the current staging status.
    
    Returns:
        Dictionary with 'staged' and 'modified' file lists
    """
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True
        )
        
        staged = []
        modified = []
        
        for line in result.stdout.strip().split('\n'):
            if len(line) >= 2:
                status = line[:2]
                file_path = line[3:]
                
                if status[0] != ' ' and status[0] != '?':  # Staged changes
                    staged.append(file_path)
                if status[1] != ' ' and status[1] != '?':  # Modified changes
                    modified.append(file_path)
        
        return {'staged': staged, 'modified': modified}
        
    except Exception:
        return {'staged': [], 'modified': []}