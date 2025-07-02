"""
Hunk applicator module for applying specific hunks to the git staging area.
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple, Set
from .diff_parser import Hunk, validate_hunk_combination, create_dependency_groups
from .logger import get_logger

logger = get_logger()

# Global tracking of file modifications
file_modification_history = {}


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
    
    # Reset file modification history for this run
    global file_modification_history
    file_modification_history = {}

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
    # Create dependency groups for sequential processing
    dependency_groups = create_dependency_groups(hunks)

    logger.debug(f"Dependency analysis: {len(dependency_groups)} groups identified")
    for i, group in enumerate(dependency_groups):
        logger.debug(f"  Group {i+1}: {len(group)} hunks")
        for hunk in group:
            deps = len(hunk.dependencies)
            dependents = len(hunk.dependents)
            logger.debug(f"    - {hunk.id} ({hunk.change_type}, deps: {deps}, dependents: {dependents})")

    # Apply groups in order
    for i, group in enumerate(dependency_groups):
        logger.hunk_debug(f"Applying group {i+1}/{len(dependency_groups)} ({len(group)} hunks)...")

        # CRITICAL FIX: Save staging state before attempting group application
        # This prevents corrupt patch failures from leaving the repository in a broken state
        group_staging_state = _save_staging_state()

        if len(group) == 1:
            # Single hunk - apply individually for better error isolation
            success = _apply_hunks_sequentially(group, base_diff)
        else:
            # Multiple interdependent hunks - try atomic application first
            success = _apply_dependency_group_atomically(group, base_diff)

            if not success:
                logger.hunk_debug("  Atomic application failed, trying sequential with smart ordering...")
                # Fallback to sequential application with dependency ordering
                success = _apply_dependency_group_sequentially(group, base_diff)

        if not success:
            logger.error(f"Failed to apply group {i+1}, restoring staging state...")
            # CRITICAL FIX: Restore staging state to prevent broken repository state
            _restore_staging_state(group_staging_state)
            return False

        logger.hunk_debug(f"✓ Group {i+1} applied successfully")
        # Track which files were modified by this group
        _track_file_modifications(group)

    # Show final file modification summary
    _show_file_modification_summary()
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
            logger.warning("No valid patch content generated")
            return False

        # Apply using git's native mechanism
        return _apply_patch_with_git(patch_content)

    except Exception as e:
        logger.error(f"Error in atomic application: {e}")
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
                logger.warning(f"Failed to apply hunk {hunk.id} ({i+1}/{len(ordered_hunks)}) via git apply")
                return False

        except Exception as e:
            logger.error(f"Error applying hunk {hunk.id}: {e}")
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
        logger.warning("Cyclic dependencies detected, using fallback ordering")
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
                logger.warning(f"Failed to apply hunk {hunk.id} ({i+1}/{len(sorted_hunks)}) via git apply")
                return False

        except Exception as e:
            logger.error(f"Error applying hunk {hunk.id}: {e}")
            return False

    return True



def _extract_files_from_patch(patch_content: str) -> Set[str]:
    """
    Extract the list of files affected by a patch.
    
    Args:
        patch_content: The patch content
        
    Returns:
        Set of file paths affected by the patch
    """
    files = set()
    lines = patch_content.split('\n')
    
    for line in lines:
        if line.startswith('diff --git'):
            # Extract file path from diff header
            # Format: diff --git a/path/to/file b/path/to/file
            parts = line.split()
            if len(parts) >= 4:
                # Remove 'b/' prefix
                file_path = parts[3][2:] if parts[3].startswith('b/') else parts[3]
                files.add(file_path)
        elif line.startswith('+++'):
            # Alternative: extract from +++ header
            # Format: +++ b/path/to/file
            parts = line.split()
            if len(parts) >= 2 and parts[1] != '/dev/null':
                file_path = parts[1][2:] if parts[1].startswith('b/') else parts[1]
                files.add(file_path)
    
    return files


def _sync_files_from_staging(file_paths: Set[str]) -> bool:
    """
    Sync specific files from staging area to working directory.
    
    Args:
        file_paths: Set of file paths to sync
        
    Returns:
        True if all files synced successfully
    """
    if not file_paths:
        # If no files specified, sync all
        try:
            subprocess.run(['git', 'checkout-index', '-f', '-a'], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    # Sync each file individually
    all_success = True
    for file_path in file_paths:
        try:
            # Use git checkout-index to sync specific file
            result = subprocess.run(
                ['git', 'checkout-index', '-f', '--', file_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to sync {file_path}: {result.stderr}")
                all_success = False
                
        except Exception as e:
            logger.error(f"Error syncing {file_path}: {e}")
            all_success = False
    
    return all_success


def _apply_patch_with_git(patch_content: str) -> bool:
    """
    Apply a patch using git's native mechanism with improved file-specific sync.

    Args:
        patch_content: The patch content to apply

    Returns:
        True if successfully applied, False otherwise
    """
    try:
        # Extract affected files from patch content
        affected_files = _extract_files_from_patch(patch_content)
        
        # Save current staging state for rollback
        staging_state = _save_staging_state()
        
        # CRITICAL FIX: Save working directory state for affected files BEFORE any patch operations
        working_dir_state = _save_working_dir_state(affected_files)
        
        # CRITICAL FIX: Also save the current staging state before applying patches
        original_staging_state = _save_staging_state()
        
        # Enhanced debug: Show file states before patch
        _debug_file_states_before_patch(affected_files, patch_content)
        
        # Track which files this patch is trying to modify
        logger.hunk_debug(f"\nPatch attempting to modify files: {', '.join(sorted(affected_files))}")
        for file_path in affected_files:
            if file_path in file_modification_history:
                logger.hunk_debug(f"  {file_path} previously modified by: {', '.join(file_modification_history[file_path])}")

        # Create temporary patch file with enhanced validation
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
            patch_file.write(patch_content)
            patch_file.flush()  # CRITICAL FIX: Ensure content is written to disk before git reads it
            # ADDITIONAL FIX: Force OS to sync the file to disk
            os.fsync(patch_file.fileno())
            patch_file_path = patch_file.name

        try:
            # CRITICAL FIX: Validate patch file is readable before attempting to apply
            try:
                with open(patch_file_path, 'r') as test_read:
                    patch_verification = test_read.read()
                    if patch_verification != patch_content:
                        raise Exception("Patch file write verification failed")
            except Exception as e:
                logger.error(f"Patch file validation failed: {e}")
                # Restore states and return failure
                _restore_working_dir_state(working_dir_state, affected_files)
                _restore_staging_state(original_staging_state)
                return False
            
            # Apply patch using git apply --index to update both staging area and working directory
            # This ensures that the working directory is immediately synchronized with the staging area
            logger.patch_debug(patch_content)
            logger.hunk_debug(f"Attempting to apply patch from file: {patch_file_path}")
            logger.hunk_debug(f"Affected files: {affected_files}")
            
            # Enhanced debug: Use verbose git apply to get detailed error info
            result = subprocess.run(
                ['git', 'apply', '-v', '--index', '--whitespace=nowarn', patch_file_path],
                capture_output=True,
                text=True,
                cwd=os.getcwd()
            )

            if result.returncode == 0:
                logger.hunk_debug("✓ Patch applied successfully via git apply --index")
                # Log which files were actually modified
                logger.hunk_debug(f"Staged files after hunk application: {', '.join(sorted(affected_files))}")
                # CRITICAL FIX: Verify working directory matches expected state after successful apply
                if _verify_working_dir_integrity(affected_files, patch_content):
                    return True
                else:
                    logger.warning("Working directory integrity check failed after successful patch apply")
                    # Don't fail here, but log the issue
                    return True
            else:
                logger.hunk_debug(f"Git apply --index failed: {result.stderr}")
                logger.hunk_debug(f"Git apply return code: {result.returncode}")
                logger.hunk_debug(f"Git apply stdout: {result.stdout}")
                
                # Enhanced debug: Analyze patch failure
                _analyze_patch_failure(patch_content, affected_files, result.stderr)
                # CRITICAL FIX: Immediately restore BOTH working directory and staging states
                logger.hunk_debug("Restoring working directory and staging states after --index failure...")
                _restore_working_dir_state(working_dir_state, affected_files)
                _restore_staging_state(original_staging_state)
                
                # If --index fails, fallback to --cached and then sync working directory
                result_cached = subprocess.run(
                    ['git', 'apply', '-v', '--cached', '--whitespace=nowarn', patch_file_path],
                    capture_output=True,
                    text=True,
                    cwd=os.getcwd()
                )
                
                if result_cached.returncode == 0:
                    logger.hunk_debug("✓ Patch applied to staging area, syncing working directory...")
                    
                    # Sync only the affected files from staging to working directory
                    # This is more precise than syncing all files with checkout-index -a
                    sync_success = _sync_files_from_staging(affected_files)
                    
                    if sync_success:
                        logger.hunk_debug("✓ Working directory synchronized for affected files")
                        return True
                    else:
                        logger.error("Failed to sync working directory")
                        # CRITICAL FIX: Restore both staging and working directory states
                        _restore_staging_state(staging_state)
                        _restore_working_dir_state(working_dir_state, affected_files)
                        return False
                else:
                    logger.error(f"Git apply --cached also failed: {result_cached.stderr}")
                    logger.hunk_debug(f"Full error output: {result_cached.stdout}")
                    logger.hunk_debug("Common reasons for patch failure:")
                    logger.hunk_debug("  - Hunk context doesn't match current file state")
                    logger.hunk_debug("  - File has been modified since diff was generated")
                    logger.hunk_debug("  - Patch is trying to modify non-existent lines")
                    logger.hunk_debug("  - Whitespace or line ending differences")
                    # CRITICAL FIX: Restore both staging and working directory states
                    _restore_staging_state(staging_state)
                    _restore_working_dir_state(working_dir_state, affected_files)
                    return False

        finally:
            # Clean up temporary file
            os.unlink(patch_file_path)

    except Exception as e:
        logger.error(f"Error applying patch with git: {e}")
        # CRITICAL FIX: Restore working directory state on any exception
        try:
            _restore_working_dir_state(working_dir_state, affected_files)
        except:
            pass
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


def _save_working_dir_state(affected_files: Set[str]) -> Dict[str, str]:
    """
    Save current working directory state for affected files with enhanced reliability.

    Args:
        affected_files: Set of file paths to save state for

    Returns:
        Dictionary mapping file paths to their content, or empty dict if unable to save
    """
    file_states = {}
    try:
        for file_path in affected_files:
            try:
                if os.path.exists(file_path):
                    # CRITICAL FIX: Use binary mode first to handle any file type
                    try:
                        with open(file_path, 'rb') as f:
                            binary_content = f.read()
                        # Try to decode as UTF-8, fall back to latin-1 if needed
                        try:
                            file_states[file_path] = binary_content.decode('utf-8')
                        except UnicodeDecodeError:
                            file_states[file_path] = binary_content.decode('latin-1')
                    except Exception:
                        # Final fallback: read as text with ignore errors
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            file_states[file_path] = f.read()
                else:
                    # Mark non-existent files as such
                    file_states[file_path] = None
                    
                # CRITICAL FIX: Verify the file was read correctly by checking length
                if file_states[file_path] is not None and os.path.exists(file_path):
                    expected_size = os.path.getsize(file_path)
                    if expected_size > 0 and len(file_states[file_path]) == 0:
                        logger.warning(f"File {file_path} appears non-empty but read as empty")
                        
            except Exception as e:
                logger.warning(f"Could not save state for {file_path}: {e}")
                # Continue with other files
        
        logger.hunk_debug(f"Successfully saved working directory state for {len(file_states)} files")
        return file_states
    except Exception as e:
        logger.error(f"Error saving working directory state: {e}")
        return {}


def _restore_working_dir_state(saved_states: Dict[str, str], affected_files: Set[str]) -> bool:
    """
    Restore working directory state for affected files with enhanced reliability.

    Args:
        saved_states: Dictionary mapping file paths to their saved content
        affected_files: Set of file paths to restore

    Returns:
        True if restoration successful
    """
    try:
        if not saved_states:
            logger.hunk_debug("No saved states to restore")
            return True

        restored_count = 0
        failed_count = 0
        
        for file_path in affected_files:
            try:
                if file_path in saved_states:
                    saved_content = saved_states[file_path]
                    if saved_content is None:
                        # File didn't exist, remove it if it exists now
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.hunk_debug(f"Removed file that shouldn't exist: {file_path}")
                            restored_count += 1
                    else:
                        # CRITICAL FIX: Create directory if it doesn't exist
                        dir_path = os.path.dirname(file_path)
                        if dir_path and not os.path.exists(dir_path):
                            os.makedirs(dir_path, exist_ok=True)
                        
                        # CRITICAL FIX: Use same encoding strategy as saving
                        try:
                            # Try to encode as UTF-8 first
                            content_bytes = saved_content.encode('utf-8')
                            with open(file_path, 'wb') as f:
                                f.write(content_bytes)
                        except UnicodeEncodeError:
                            # Fallback to latin-1 if UTF-8 fails
                            content_bytes = saved_content.encode('latin-1')
                            with open(file_path, 'wb') as f:
                                f.write(content_bytes)
                        
                        # CRITICAL FIX: Verify the file was written correctly
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                written_content = f.read()
                            if len(written_content) != len(saved_content):
                                logger.warning(f"File {file_path} restoration size mismatch: expected {len(saved_content)}, got {len(written_content)}")
                        except Exception:
                            pass  # Verification failed, but file was written
                        
                        logger.hunk_debug(f"Restored working directory state for: {file_path}")
                        restored_count += 1
                else:
                    logger.warning(f"No saved state found for {file_path}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Could not restore {file_path}: {e}")
                failed_count += 1
                # Continue with other files

        logger.hunk_debug(f"Working directory restoration: {restored_count} restored, {failed_count} failed out of {len(affected_files)} files")
        return failed_count == 0
    except Exception as e:
        logger.error(f"Error during working directory restoration: {e}")
        return False


def _verify_working_dir_integrity(affected_files: Set[str], patch_content: str) -> bool:
    """
    Verify that working directory files are in a valid state after patch application.
    
    Args:
        affected_files: Set of file paths that were modified
        patch_content: The patch content that was applied
        
    Returns:
        True if working directory appears to be in good state
    """
    try:
        issues_found = 0
        total_files = len(affected_files)
        
        for file_path in affected_files:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # ENHANCED: Check for common corruption patterns with better heuristics
                    if file_path.endswith(('.js', '.ts', '.jsx', '.tsx', '.svelte', '.vue')):
                        # More sophisticated check for missing closing braces in JavaScript-like files
                        if content.strip():
                            lines = content.splitlines()
                            if lines:
                                last_line = lines[-1].strip()
                                
                                # Count braces to detect imbalance
                                open_braces = content.count('{')
                                close_braces = content.count('}')
                                
                                # Check if file ends abruptly
                                ends_properly = last_line.endswith(('}', ';', ')', ']', '>'))
                                
                                # CRITICAL FIX: More robust detection
                                if open_braces > close_braces:
                                    logger.warning(f"File {file_path} has unmatched opening braces ({open_braces} open, {close_braces} close)")
                                    issues_found += 1
                                elif not ends_properly and len(lines) > 10:
                                    # Only flag files that are substantial and don't end properly
                                    # Check if the last line looks incomplete
                                    if any(keyword in last_line.lower() for keyword in ['function', 'if', 'for', 'while', 'export', 'import', 'const', 'let', 'var']):
                                        logger.warning(f"File {file_path} may end abruptly - last line: '{last_line}'")
                                        issues_found += 1
                                elif not content.endswith('\n') and '\\' not in content[-10:]:
                                    # File doesn't end with newline and no "No newline" marker nearby
                                    logger.warning(f"File {file_path} missing trailing newline without proper marker")
                                    issues_found += 1
                    
                    # Check for completely empty files that shouldn't be empty
                    if os.path.getsize(file_path) == 0 and 'delete' not in patch_content.lower():
                        logger.warning(f"File {file_path} is unexpectedly empty")
                        issues_found += 1
                        
            except Exception as e:
                logger.warning(f"Could not verify integrity of {file_path}: {e}")
                issues_found += 1
        
        if issues_found > 0:
            logger.hunk_debug(f"Working directory integrity check: {issues_found} potential issues found out of {total_files} files")
            return False
        else:
            logger.hunk_debug(f"Working directory integrity check: All {total_files} files appear valid")
            return True
            
    except Exception as e:
        logger.error(f"Error during working directory integrity check: {e}")
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
            logger.error(f"Could not generate valid patch for hunk {hunk.id}")
            return False

        # Apply using git's native mechanism
        return _apply_patch_with_git(patch_content)

    except Exception as e:
        logger.error(f"Error applying hunk {hunk.id}: {e}")
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




def reset_staging_area():
    """Reset the staging area to match HEAD."""
    try:
        result = subprocess.run(
            ['git', 'reset', 'HEAD'],
            capture_output=True,
            text=True,
            check=False
        )
        # Also reset file modification history
        global file_modification_history
        file_modification_history = {}
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


def _debug_file_states_before_patch(affected_files: Set[str], patch_content: str):
    """
    Debug helper to show file states before applying patch.
    
    Args:
        affected_files: Files that will be affected by the patch
        patch_content: The patch content to be applied
    """
    try:
        for file_path in affected_files:
            logger.hunk_debug(f"\n===== FILE STATE BEFORE PATCH: {file_path} =====")
            
            # Show current file content with line numbers
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Extract context from patch for this file
                patch_lines = patch_content.split('\n')
                in_file_section = False
                patch_hunks = []
                current_hunk = []
                
                for line in patch_lines:
                    if line.startswith('diff --git') and f'b/{file_path}' in line:
                        in_file_section = True
                    elif line.startswith('diff --git') and in_file_section:
                        break
                    elif in_file_section and line.startswith('@@'):
                        if current_hunk:
                            patch_hunks.append(current_hunk)
                        current_hunk = [line]
                    elif in_file_section and current_hunk:
                        current_hunk.append(line)
                
                if current_hunk:
                    patch_hunks.append(current_hunk)
                
                # For each hunk, show the relevant file context
                for hunk in patch_hunks:
                    if hunk and hunk[0].startswith('@@'):
                        # Parse hunk header
                        import re
                        match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', hunk[0])
                        if match:
                            start_line = int(match.group(1))
                            context_start = max(0, start_line - 4)
                            context_end = min(len(lines), start_line + 15)
                            
                            logger.hunk_debug(f"\nFile content around line {start_line}:")
                            for i in range(context_start, context_end):
                                line_num = i + 1
                                line_content = lines[i].rstrip('\n') if i < len(lines) else ''
                                logger.hunk_debug(f"{line_num:4d}: {line_content}")
                            
                            logger.hunk_debug("\nPatch expects:")
                            for patch_line in hunk[1:11]:  # Show first 10 lines of hunk
                                logger.hunk_debug(f"      {patch_line}")
            else:
                logger.hunk_debug(f"File does not exist yet: {file_path}")
            
            # Show git index vs working directory state
            logger.hunk_debug(f"\n===== GIT STATE FOR {file_path} =====")
            
            # Check index state
            index_result = subprocess.run(
                ['git', 'diff', '--cached', '--', file_path],
                capture_output=True,
                text=True
            )
            if index_result.stdout:
                logger.hunk_debug("File has staged changes:")
                for line in index_result.stdout.split('\n')[:20]:
                    logger.hunk_debug(f"  STAGED: {line}")
            else:
                logger.hunk_debug("No staged changes for this file")
            
            # Check working directory state
            wd_result = subprocess.run(
                ['git', 'diff', '--', file_path],
                capture_output=True,
                text=True
            )
            if wd_result.stdout:
                logger.hunk_debug("File has unstaged changes:")
                for line in wd_result.stdout.split('\n')[:20]:
                    logger.hunk_debug(f"  UNSTAGED: {line}")
            else:
                logger.hunk_debug("No unstaged changes for this file")
                
    except Exception as e:
        logger.error(f"Error in debug file states: {e}")


def _analyze_patch_failure(patch_content: str, affected_files: Set[str], error_msg: str):
    """
    Analyze why a patch failed to apply by comparing expected vs actual content.
    
    Args:
        patch_content: The patch that failed to apply
        affected_files: Files that were supposed to be affected
        error_msg: The error message from git apply
    """
    try:
        logger.hunk_debug("\n===== PATCH FAILURE ANALYSIS =====")
        logger.hunk_debug(f"Error message: {error_msg}")
        
        # Parse error to find specific line failures
        import re
        error_matches = re.findall(r'error: patch failed: ([^:]+):(\d+)', error_msg)
        
        for file_path, line_num in error_matches:
            logger.hunk_debug(f"\nPatch failed at {file_path}:{line_num}")
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                line_idx = int(line_num) - 1
                context_start = max(0, line_idx - 3)
                context_end = min(len(lines), line_idx + 4)
                
                logger.hunk_debug("Actual file content:")
                for i in range(context_start, context_end):
                    marker = '>>>' if i == line_idx else '   '
                    line_content = lines[i].rstrip('\n') if i < len(lines) else ''
                    logger.hunk_debug(f"{marker} {i+1:4d}: {line_content}")
                
                # Extract what patch expected
                _show_patch_expectations(patch_content, file_path, int(line_num))
        
        # Check for common issues
        if "does not match index" in error_msg:
            logger.hunk_debug("\nIssue: File in working directory differs from index")
            logger.hunk_debug("This usually means the file was modified after staging")
        
        if "No such file or directory" in error_msg:
            logger.hunk_debug("\nIssue: Patch expects a file that doesn't exist")
        
        if "already exists" in error_msg:
            logger.hunk_debug("\nIssue: Patch tries to create a file that already exists")
            
    except Exception as e:
        logger.error(f"Error analyzing patch failure: {e}")


def _show_patch_expectations(patch_content: str, file_path: str, target_line: int):
    """
    Show what the patch expected to find at a specific line.
    
    Args:
        patch_content: The full patch content
        file_path: The file path
        target_line: The line number where patch failed
    """
    try:
        logger.hunk_debug(f"\nPatch expectations for line {target_line}:")
        
        lines = patch_content.split('\n')
        in_file = False
        current_line = 0
        
        for i, line in enumerate(lines):
            if f'b/{file_path}' in line:
                in_file = True
            elif in_file and line.startswith('diff --git'):
                break
            elif in_file and line.startswith('@@'):
                # Parse hunk header
                import re
                match = re.match(r'@@ -(\d+),?\d* \+\d+,?\d* @@', line)
                if match:
                    current_line = int(match.group(1))
            elif in_file and current_line > 0:
                if line.startswith(' '):
                    # Context line
                    if abs(current_line - target_line) <= 3:
                        logger.hunk_debug(f"  Expected context at {current_line}: {line[1:]}")
                    current_line += 1
                elif line.startswith('-'):
                    # Line to be removed
                    if abs(current_line - target_line) <= 3:
                        logger.hunk_debug(f"  Expected to remove at {current_line}: {line[1:]}")
                    current_line += 1
                elif line.startswith('+'):
                    # Line to be added (doesn't increment current_line)
                    if abs(current_line - target_line) <= 3:
                        logger.hunk_debug(f"  Expected to add after {current_line}: {line[1:]}")
                        
    except Exception as e:
        logger.error(f"Error showing patch expectations: {e}")


def _track_file_modifications(hunks: List[Hunk]):
    """
    Track which hunks modified which files.
    
    Args:
        hunks: List of hunks that were successfully applied
    """
    global file_modification_history
    for hunk in hunks:
        if hunk.file_path not in file_modification_history:
            file_modification_history[hunk.file_path] = []
        file_modification_history[hunk.file_path].append(hunk.id)
        logger.hunk_debug(f"File {hunk.file_path} modified by hunk {hunk.id}")


def _show_file_modification_summary():
    """
    Show summary of all file modifications.
    """
    global file_modification_history
    if file_modification_history:
        logger.hunk_debug("\n===== FILE MODIFICATION SUMMARY =====")
        for file_path, hunk_ids in file_modification_history.items():
            logger.hunk_debug(f"{file_path}: modified by hunks {', '.join(hunk_ids)}")
