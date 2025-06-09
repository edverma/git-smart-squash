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
    Apply specific hunks to the git staging area using sequential application.
    
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
    
    # Apply hunks sequentially for better reliability
    return _apply_hunks_sequentially(hunks_to_apply, base_diff)


def _apply_hunks_sequentially(hunks: List[Hunk], base_diff: str) -> bool:
    """
    Apply hunks one by one for better reliability and error isolation.
    
    Args:
        hunks: List of hunks to apply
        base_diff: Original full diff output
        
    Returns:
        True if all hunks applied successfully, False otherwise
    """
    from .diff_parser import create_hunk_patch
    
    # Sort hunks by file and line number for consistent application order
    sorted_hunks = sorted(hunks, key=lambda h: (h.file_path, h.start_line))
    
    for i, hunk in enumerate(sorted_hunks):
        try:
            # Create a patch for this single hunk
            single_hunk_patch = create_hunk_patch([hunk], base_diff)
            
            if not single_hunk_patch.strip():
                print(f"Warning: Empty patch generated for hunk {hunk.id}")
                continue
            
            # Validate the patch before applying
            if not _validate_patch_format(single_hunk_patch):
                print(f"Error: Invalid patch format for hunk {hunk.id}")
                return False
            
            # Apply this individual hunk
            success = _apply_patch_to_staging(single_hunk_patch)
            if not success:
                print(f"Failed to apply hunk {hunk.id} ({i+1}/{len(sorted_hunks)})")
                return False
            
        except Exception as e:
            print(f"Error applying hunk {hunk.id}: {e}")
            return False
    
    return True


def _validate_patch_format(patch_content: str) -> bool:
    """
    Validate that a patch has the correct format before applying.
    
    Args:
        patch_content: The patch content to validate
        
    Returns:
        True if patch format is valid, False otherwise
    """
    lines = patch_content.strip().split('\n')
    
    if not lines:
        return False
    
    # Must start with diff --git
    if not lines[0].startswith('diff --git'):
        return False
    
    # Must have at least one @@ hunk header
    has_hunk = any(line.startswith('@@') for line in lines)
    if not has_hunk:
        return False
    
    # Check for basic file header structure
    has_file_markers = any(line.startswith('---') for line in lines) and \
                      any(line.startswith('+++') for line in lines)
    
    if not has_file_markers:
        return False
    
    return True


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
            # Apply the patch to the staging area with tolerant flags
            result = subprocess.run(
                ['git', 'apply', '--cached', '--whitespace=nowarn', '--ignore-space-change', '--ignore-whitespace', patch_file_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # Try with even more permissive flags
                result = subprocess.run(
                    ['git', 'apply', '--cached', '--whitespace=fix', '--ignore-space-change', '--ignore-whitespace', patch_file_path],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    print(f"Git apply failed even with permissive flags: {result.stderr}")
                    # Only show debug info for individual hunk failures, not the massive combined patches
                    if len(patch_content) < 1000:  # Only show debug for small patches
                        print(f"Debug: Patch content:\n{patch_content}")
                    else:
                        print(f"Debug: Large patch ({len(patch_content)} chars), first 200 chars:\n{patch_content[:200]}")
                    return False
                else:
                    print("✓ Applied with whitespace fixes")
            
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
    Apply hunks using the hunk-based approach only.
    
    Args:
        hunk_ids: List of hunk IDs to apply
        hunks_by_id: Dictionary mapping hunk IDs to Hunk objects
        base_diff: Original full diff output
        
    Returns:
        True if successful, False otherwise
    """
    return apply_hunks(hunk_ids, hunks_by_id, base_diff)


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