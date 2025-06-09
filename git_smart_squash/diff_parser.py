"""
Diff parser module for extracting individual hunks from git diff output.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Hunk:
    """Represents an individual hunk (change block) from a git diff."""
    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    context: str


def parse_diff(diff_output: str, context_lines: int = 3) -> List[Hunk]:
    """
    Parse git diff output into individual hunks.
    
    Args:
        diff_output: Raw git diff output string
        
    Returns:
        List of Hunk objects representing individual change blocks
    """
    hunks = []
    current_file = None
    
    lines = diff_output.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for file header
        if line.startswith('diff --git'):
            # Extract file path from the diff header
            # Format: diff --git a/path/to/file b/path/to/file
            match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if match:
                current_file = match.group(2)  # Use the 'b/' path (after changes)
        
        # Check for hunk header
        elif line.startswith('@@') and current_file:
            hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if hunk_match:
                old_start = int(hunk_match.group(1))
                old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                
                # Collect hunk content
                hunk_content_lines = [line]  # Include the @@ line
                i += 1
                
                # Read until next file header, hunk header, or end
                while i < len(lines):
                    next_line = lines[i]
                    if (next_line.startswith('diff --git') or 
                        next_line.startswith('@@') or
                        (next_line.startswith('\\') and 'No newline' in next_line)):
                        # Handle "\ No newline at end of file"
                        if next_line.startswith('\\'):
                            hunk_content_lines.append(next_line)
                            i += 1
                        break
                    hunk_content_lines.append(next_line)
                    i += 1
                
                # Create hunk
                hunk_content = '\n'.join(hunk_content_lines)
                
                # Calculate line range for the hunk ID
                # Use the new file line numbers for the range
                end_line = new_start + max(0, new_count - 1)
                
                hunk_id = f"{current_file}:{new_start}-{end_line}"
                
                # Get context around the hunk
                context = get_hunk_context(current_file, new_start, end_line, context_lines)
                
                hunk = Hunk(
                    id=hunk_id,
                    file_path=current_file,
                    start_line=new_start,
                    end_line=end_line,
                    content=hunk_content,
                    context=context
                )
                
                hunks.append(hunk)
                continue  # Don't increment i, we already did it in the while loop
        
        i += 1
    
    return hunks


def get_hunk_context(file_path: str, start_line: int, end_line: int, context_lines: int = 3) -> str:
    """
    Extract surrounding code context for better AI understanding.
    
    Args:
        file_path: Path to the file
        start_line: Starting line number of the hunk
        end_line: Ending line number of the hunk
        context_lines: Number of lines before and after to include
        
    Returns:
        String containing the context around the hunk
    """
    try:
        # Read the current file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = f.readlines()
        
        # Calculate context boundaries
        context_start = max(0, start_line - context_lines - 1)  # -1 for 0-based indexing
        context_end = min(len(file_lines), end_line + context_lines)
        
        # Extract context lines
        context_lines_list = file_lines[context_start:context_end]
        
        # Add line numbers for clarity
        numbered_lines = []
        for i, line in enumerate(context_lines_list, start=context_start + 1):
            prefix = ">>> " if start_line <= i <= end_line else "    "
            numbered_lines.append(f"{prefix}{i:4d}: {line.rstrip()}")
        
        return '\n'.join(numbered_lines)
        
    except (FileNotFoundError, IOError):
        # If we can't read the file, return minimal context
        return f"File: {file_path} (lines {start_line}-{end_line})"


def create_hunk_patch(hunks: List[Hunk], base_diff: str) -> str:
    """
    Create a patch file containing only the specified hunks.
    
    Args:
        hunks: List of hunks to include in the patch
        base_diff: Original full diff output
        
    Returns:
        Patch content that can be applied with git apply
    """
    if not hunks:
        return ""
    
    # Group hunks by file
    hunks_by_file = {}
    for hunk in hunks:
        if hunk.file_path not in hunks_by_file:
            hunks_by_file[hunk.file_path] = []
        hunks_by_file[hunk.file_path].append(hunk)
    
    patch_lines = []
    base_lines = base_diff.split('\n')
    
    for file_path, file_hunks in hunks_by_file.items():
        # Find the file header in the original diff
        file_header_start = None
        for i, line in enumerate(base_lines):
            if line.startswith('diff --git') and file_path in line:
                file_header_start = i
                break
        
        if file_header_start is None:
            continue
        
        # Add file header lines (diff --git, index, ---, +++)
        j = file_header_start
        while j < len(base_lines) and not base_lines[j].startswith('@@'):
            patch_lines.append(base_lines[j])
            j += 1
        
        # Add the hunks for this file
        for hunk in sorted(file_hunks, key=lambda h: h.start_line):
            patch_lines.append(hunk.content)
    
    return '\n'.join(patch_lines)


def validate_hunk_combination(hunks: List[Hunk]) -> Tuple[bool, str]:
    """
    Validate that a combination of hunks can be applied together.
    
    Args:
        hunks: List of hunks to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not hunks:
        return True, ""
    
    # Group by file and check for overlaps
    hunks_by_file = {}
    for hunk in hunks:
        if hunk.file_path not in hunks_by_file:
            hunks_by_file[hunk.file_path] = []
        hunks_by_file[hunk.file_path].append(hunk)
    
    for file_path, file_hunks in hunks_by_file.items():
        # Sort hunks by start line
        sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
        
        # Check for overlapping hunks
        for i in range(len(sorted_hunks) - 1):
            current_hunk = sorted_hunks[i]
            next_hunk = sorted_hunks[i + 1]
            
            if current_hunk.end_line >= next_hunk.start_line:
                return False, f"Overlapping hunks in {file_path}: {current_hunk.id} and {next_hunk.id}"
    
    return True, ""