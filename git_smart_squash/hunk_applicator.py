"""
Hunk applicator module for applying specific hunks to the git staging area.
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple
from .diff_parser import Hunk, validate_hunk_combination, create_dependency_groups


class HunkApplicatorError(Exception):
    """Custom exception for hunk application errors."""
    pass


def apply_hunks(hunk_ids: List[str], hunks_by_id: Dict[str, Hunk], base_diff: str) -> bool:
    """
    Apply specific hunks to the git staging area using dependency-aware grouping.

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

    # Use dependency-aware application for better handling of complex changes
    return _apply_hunks_with_dependencies(hunks_to_apply, base_diff)


def _apply_hunks_with_dependencies(hunks: List[Hunk], base_diff: str) -> bool:
    """
    Apply hunks using dependency-aware grouping for better handling of complex changes.

    Args:
        hunks: List of hunks to apply
        base_diff: Original full diff output

    Returns:
        True if all hunks applied successfully, False otherwise
    """
    # Create dependency groups
    dependency_groups = create_dependency_groups(hunks)

    print(f"Dependency analysis: {len(dependency_groups)} groups identified")
    for i, group in enumerate(dependency_groups):
        print(f"  Group {i+1}: {len(group)} hunks")
        for hunk in group:
            deps = len(hunk.dependencies)
            dependents = len(hunk.dependents)
            print(f"    - {hunk.id} ({hunk.change_type}, deps: {deps}, dependents: {dependents})")

    # Apply groups in order
    for i, group in enumerate(dependency_groups):
        print(f"Applying group {i+1}/{len(dependency_groups)} ({len(group)} hunks)...")

        if len(group) == 1:
            # Single hunk - apply individually for better error isolation
            success = _apply_hunks_sequentially(group, base_diff)
        else:
            # Multiple interdependent hunks - try atomic application first
            success = _apply_dependency_group_atomically(group, base_diff)

            if not success:
                print("  Atomic application failed, trying sequential with smart ordering...")
                # Fallback to sequential application with dependency ordering
                success = _apply_dependency_group_sequentially(group, base_diff)

        if not success:
            print(f"Failed to apply group {i+1}")
            return False

        print(f"✓ Group {i+1} applied successfully")

    return True


def _apply_dependency_group_atomically(hunks: List[Hunk], base_diff: str) -> bool:
    """
    Apply a dependency group using git's native patch application with proper line number calculation.

    Args:
        hunks: List of hunks in the dependency group
        base_diff: Original full diff output

    Returns:
        True if successful, False otherwise
    """
    try:
        # Generate valid patch with corrected line numbers
        from .diff_parser import _create_valid_git_patch
        patch_content = _create_valid_git_patch(hunks, base_diff)

        if not patch_content.strip():
            print("No valid patch content generated")
            return False

        # Apply using git's native mechanism
        return _apply_patch_with_git(patch_content)

    except Exception as e:
        print(f"Error in atomic application: {e}")
        return False


def _apply_dependency_group_sequentially(hunks: List[Hunk], base_diff: str) -> bool:
    """
    Apply hunks in a dependency group sequentially using git native mechanisms.

    Args:
        hunks: List of hunks in the dependency group
        base_diff: Original full diff output

    Returns:
        True if successful, False otherwise
    """
    # Order hunks by dependencies (topological sort)
    ordered_hunks = _topological_sort_hunks(hunks)

    if not ordered_hunks:
        # Fallback to simple ordering if topological sort fails
        ordered_hunks = sorted(hunks, key=lambda h: (h.file_path, h.start_line))

    # Apply hunks in dependency order using git native mechanisms
    for i, hunk in enumerate(ordered_hunks):
        try:
            success = _relocate_and_apply_hunk(hunk, base_diff)
            if not success:
                print(f"Failed to apply hunk {hunk.id} ({i+1}/{len(ordered_hunks)}) via git apply")
                return False

        except Exception as e:
            print(f"Error applying hunk {hunk.id}: {e}")
            return False

    return True


def _topological_sort_hunks(hunks: List[Hunk]) -> List[Hunk]:
    """
    Sort hunks based on their dependencies using topological sort.

    Args:
        hunks: List of hunks to sort

    Returns:
        List of hunks in dependency order, or empty list if cyclic dependencies
    """
    # Build hunk map for quick lookups
    hunk_map = {hunk.id: hunk for hunk in hunks}
    hunk_ids = set(hunk.id for hunk in hunks)

    # Calculate in-degrees (number of dependencies within this group)
    in_degree = {}
    for hunk in hunks:
        # Only count dependencies that are within this group
        local_deps = hunk.dependencies & hunk_ids
        in_degree[hunk.id] = len(local_deps)

    # Start with hunks that have no dependencies within the group
    queue = [hunk_id for hunk_id in hunk_ids if in_degree[hunk_id] == 0]
    result = []

    while queue:
        current_id = queue.pop(0)
        result.append(hunk_map[current_id])

        # Reduce in-degree for dependents
        current_hunk = hunk_map[current_id]
        for dependent_id in current_hunk.dependents:
            if dependent_id in hunk_ids:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

    # Check for cycles
    if len(result) != len(hunks):
        print("Warning: Cyclic dependencies detected, using fallback ordering")
        return []

    return result


def _apply_hunks_sequentially(hunks: List[Hunk], base_diff: str) -> bool:
    """
    Apply hunks one by one using git native mechanisms for better reliability.

    Args:
        hunks: List of hunks to apply
        base_diff: Original full diff output

    Returns:
        True if all hunks applied successfully, False otherwise
    """
    # Sort hunks by file and line number for consistent application order
    sorted_hunks = sorted(hunks, key=lambda h: (h.file_path, h.start_line))

    for i, hunk in enumerate(sorted_hunks):
        try:
            # Use git native patch application
            success = _relocate_and_apply_hunk(hunk, base_diff)
            if not success:
                print(f"Failed to apply hunk {hunk.id} ({i+1}/{len(sorted_hunks)}) via git apply")
                return False

        except Exception as e:
            print(f"Error applying hunk {hunk.id}: {e}")
            return False

    return True



def _apply_patch_with_git(patch_content: str) -> bool:
    """
    Apply a patch using git's native mechanism.

    Args:
        patch_content: The patch content to apply

    Returns:
        True if successfully applied, False otherwise
    """
    try:
        # Save current staging state for rollback
        staging_state = _save_staging_state()

        # Create temporary patch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
            patch_file.write(patch_content)
            patch_file.flush()  # CRITICAL FIX: Ensure content is written to disk before git reads it
            patch_file_path = patch_file.name

        try:
            # Apply patch using git apply --index to update both staging area and working directory
            # This ensures that the working directory is immediately synchronized with the staging area
            result = subprocess.run(
                ['git', 'apply', '--index', '--whitespace=nowarn', patch_file_path],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )

            if result.returncode == 0:
                print("✓ Patch applied successfully via git apply")
                return True
            else:
                print(f"Git apply failed: {result.stderr}")
                # If --index fails, fallback to --cached and then sync working directory
                result_cached = subprocess.run(
                    ['git', 'apply', '--cached', '--whitespace=nowarn', patch_file_path],
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd()
                )
                
                if result_cached.returncode == 0:
                    print("✓ Patch applied to staging area, syncing working directory...")
                    # Force working directory to match staging area
                    try:
                        subprocess.run(['git', 'checkout-index', '-f', '-a'], check=True, capture_output=True)
                        print("✓ Working directory synchronized")
                        return True
                    except subprocess.CalledProcessError as sync_error:
                        print(f"Failed to sync working directory: {sync_error}")
                        # Rollback staging state
                        _restore_staging_state(staging_state)
                        return False
                else:
                    print(f"Git apply --cached also failed: {result_cached.stderr}")
                    # Rollback staging state
                    _restore_staging_state(staging_state)
                    return False

        finally:
            # Clean up temporary file
            os.unlink(patch_file_path)

    except Exception as e:
        print(f"Error applying patch with git: {e}")
        return False


def _save_staging_state() -> Optional[str]:
    """
    Save current staging state for rollback.

    Returns:
        Staging state identifier or None if unable to save
    """
    try:
        # Get current staged diff
        result = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except:
        return None


def _restore_staging_state(saved_state: Optional[str]) -> bool:
    """
    Restore staging state from saved state.

    Args:
        saved_state: Previously saved staging state

    Returns:
        True if restoration successful
    """
    try:
        if saved_state is None:
            return True

        # Reset staging area
        subprocess.run(['git', 'reset', 'HEAD'], capture_output=True, check=True)

        # If there was staged content, reapply it
        if saved_state.strip():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
                patch_file.write(saved_state)
                patch_file_path = patch_file.name

            try:
                subprocess.run(
                    ['git', 'apply', '--cached', patch_file_path],
                    capture_output=True,
                    check=True
                )
            finally:
                os.unlink(patch_file_path)

        return True
    except:
        return False


def _relocate_and_apply_hunk(hunk: Hunk, base_diff: str) -> bool:
    """
    Apply a hunk using git's native patch application instead of direct file modification.

    Args:
        hunk: The hunk to apply
        base_diff: Original full diff for context

    Returns:
        True if successfully applied, False otherwise
    """
    try:
        # Generate valid patch for single hunk
        from .diff_parser import _create_valid_git_patch
        patch_content = _create_valid_git_patch([hunk], base_diff)

        if not patch_content.strip():
            print(f"Could not generate valid patch for hunk {hunk.id}")
            return False

        # Apply using git's native mechanism
        return _apply_patch_with_git(patch_content)

    except Exception as e:
        print(f"Error applying hunk {hunk.id}: {e}")
        return False


def _parse_hunk_content(hunk: Hunk) -> Tuple[List[str], List[str], List[str]]:
    """
    Parse hunk content to extract additions, deletions, and context lines.

    Args:
        hunk: The hunk to parse

    Returns:
        Tuple of (additions, deletions, context_lines)
    """
    additions = []
    deletions = []
    context_lines = []

    for line in hunk.content.split('\n')[1:]:  # Skip header
        # CRITICAL FIX: Don't filter out empty lines - they're significant in git diffs
        if line.startswith('+') and not line.startswith('+++'):
            additions.append(line[1:])  # Remove + prefix
        elif line.startswith('-') and not line.startswith('---'):
            deletions.append(line[1:])  # Remove - prefix
        elif line.startswith(' '):
            context_lines.append(line[1:])  # Remove space prefix
        elif not line:
            # Empty lines are context lines (preserve file structure)
            context_lines.append('')

    return additions, deletions, context_lines


def _is_file_operation_hunk(hunk: Hunk) -> bool:
    """
    Determine if a hunk represents a file creation or deletion operation.

    Args:
        hunk: The hunk to check

    Returns:
        True if this is a file operation hunk
    """
    # Check if this is a file deletion (hunk ID shows 0-0 range)
    if hunk.start_line == 0 and hunk.end_line == 0:
        return True

    # Check if file doesn't exist (creation case)
    if not os.path.exists(hunk.file_path):
        return True

    # Check hunk content for file operation markers
    hunk_content = hunk.content
    if 'new file mode' in hunk_content or 'deleted file mode' in hunk_content:
        return True

    # Check if hunk contains only additions (likely file creation)
    additions, deletions, _ = _parse_hunk_content(hunk)
    if not deletions and len(additions) > 5:  # Threshold for "new file"
        return True

    return False


def _apply_file_operation_hunk(hunk: Hunk, additions: list, deletions: list) -> bool:
    """
    Handle file creation and deletion operations specially.

    Args:
        hunk: The hunk representing file operation
        additions: Lines being added
        deletions: Lines being deleted

    Returns:
        True if operation succeeded
    """
    try:
        # File deletion case (including 0-0 range hunks)
        if hunk.start_line == 0 and hunk.end_line == 0:
            if os.path.exists(hunk.file_path):
                print(f"Deleting file: {hunk.file_path}")
                result = subprocess.run(['git', 'rm', hunk.file_path], capture_output=True, text=True)
                return result.returncode == 0
            else:
                print(f"File {hunk.file_path} already deleted, staging deletion")
                # File is already deleted from filesystem, but we need to stage the deletion
                result = subprocess.run(['git', 'add', hunk.file_path], capture_output=True, text=True)
                return result.returncode == 0

        # File creation case
        elif not os.path.exists(hunk.file_path) and additions:
            print(f"Creating new file: {hunk.file_path}")
            os.makedirs(os.path.dirname(hunk.file_path), exist_ok=True)
            with open(hunk.file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(additions) + '\n' if additions else '')

            # Stage the new file
            result = subprocess.run(['git', 'add', hunk.file_path], capture_output=True, text=True)
            return result.returncode == 0

        # Check if this is actually a content modification that should be handled differently
        elif os.path.exists(hunk.file_path):
            # Fall back to git native patch application
            from .diff_parser import _create_valid_git_patch
            patch_content = _create_valid_git_patch([hunk], "")
            if patch_content.strip():
                return _apply_patch_with_git(patch_content)
            return False

        else:
            print(f"Unclear file operation for {hunk.file_path}")
            return False

    except Exception as e:
        print(f"Error handling file operation for {hunk.file_path}: {e}")
        return False




def _lines_match_fuzzy(file_lines: list, target_lines: list, threshold: float = 0.7) -> bool:
    """
    Check if lines match with fuzzy matching (handles whitespace, etc.).

    Args:
        file_lines: Lines from the current file
        target_lines: Lines we're trying to match
        threshold: Minimum match ratio (0.0 to 1.0)

    Returns:
        True if lines match above threshold
    """
    if len(file_lines) != len(target_lines):
        return False

    if not target_lines:
        return True

    matches = 0
    for file_line, target_line in zip(file_lines, target_lines):
        # Normalize whitespace and compare
        if file_line.strip() == target_line.strip():
            matches += 1
        # Also allow partial matches for similar content
        elif target_line.strip() in file_line.strip() or file_line.strip() in target_line.strip():
            matches += 0.5

    match_ratio = matches / len(target_lines)
    return match_ratio >= threshold




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
