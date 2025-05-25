"""Shared utilities for grouping strategies."""

from typing import Set


def extract_scope_from_files(files: Set[str]) -> str:
    """
    Extract a scope from file paths by finding common directory.
    
    Args:
        files: Set of file paths
        
    Returns:
        Common directory name as scope, or empty string
    """
    if not files:
        return ""
    
    file_list = list(files)
    if len(file_list) == 1:
        # Single file - use parent directory
        parts = file_list[0].split('/')
        if len(parts) > 1:
            return parts[-2]
        return ""
    
    # Multiple files - find common prefix
    common_parts = []
    first_parts = file_list[0].split('/')
    
    for i, part in enumerate(first_parts[:-1]):  # Exclude filename
        if all(len(f.split('/')) > i and f.split('/')[i] == part for f in file_list):
            common_parts.append(part)
        else:
            break
    
    if common_parts:
        # Use the last common directory as scope
        return common_parts[-1]
    
    return ""