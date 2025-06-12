"""
Diff parser module for extracting individual hunks from git diff output.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict


@dataclass
class Hunk:
    """Represents an individual hunk (change block) from a git diff."""
    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    context: str
    dependencies: Set[str] = field(default_factory=set)  # Hunk IDs this depends on
    dependents: Set[str] = field(default_factory=set)    # Hunk IDs that depend on this
    change_type: str = field(default="modification")     # addition, deletion, modification, import, export


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
                
                # Analyze change type
                change_type = analyze_hunk_change_type(hunk_content, current_file)
                
                hunk = Hunk(
                    id=hunk_id,
                    file_path=current_file,
                    start_line=new_start,
                    end_line=end_line,
                    content=hunk_content,
                    context=context,
                    change_type=change_type
                )
                
                hunks.append(hunk)
                continue  # Don't increment i, we already did it in the while loop
        
        i += 1
    
    # Analyze dependencies between hunks
    analyze_hunk_dependencies(hunks)
    
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
    Create a patch file containing only the specified hunks with proper line number calculation.
    
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
    
    # Parse the base diff to extract file headers and validate hunks
    base_lines = base_diff.split('\n')
    file_headers = {}
    file_hunks_in_base = {}  # Track all hunks in base diff for validation
    
    i = 0
    current_file = None
    while i < len(base_lines):
        line = base_lines[i]
        if line.startswith('diff --git'):
            # Extract file path from diff header
            match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if match:
                current_file = match.group(2)
                file_headers[current_file] = []
                file_hunks_in_base[current_file] = []
                header_lines = [line]
                i += 1
                
                # Collect all header lines until first @@ or next diff
                while i < len(base_lines):
                    next_line = base_lines[i]
                    if next_line.startswith('@@') or next_line.startswith('diff --git'):
                        break
                    header_lines.append(next_line)
                    i += 1
                
                file_headers[current_file] = header_lines
                continue
        elif line.startswith('@@') and current_file:
            # Track hunks in base diff
            file_hunks_in_base[current_file].append(line)
        i += 1
    
    # Build the patch with validation
    patch_parts = []
    
    for file_path, file_hunks in hunks_by_file.items():
        # Add file header
        if file_path in file_headers:
            patch_parts.extend(file_headers[file_path])
        else:
            # Fallback header if not found in base diff
            patch_parts.extend([
                f"diff --git a/{file_path} b/{file_path}",
                f"index 0000000..1111111 100644",
                f"--- a/{file_path}",
                f"+++ b/{file_path}"
            ])
        
        # Sort hunks and validate before adding
        sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
        
        # Use dependency-aware patch generation
        if len(sorted_hunks) > 1:
            # Multiple hunks in same file - use dependency-aware line number calculation
            adjustments = _calculate_line_number_adjustments(sorted_hunks)
            
            for hunk in sorted_hunks:
                adjusted_old_start, adjusted_new_start = adjustments[hunk.id]
                hunk_lines = hunk.content.split('\n')
                
                if hunk_lines and hunk_lines[0].startswith('@@'):
                    # Recalculate header with proper line numbers
                    additions, deletions = _count_hunk_changes(hunk)
                    context = sum(1 for line in hunk_lines[1:] if line.startswith(' '))
                    
                    old_count = deletions + context
                    new_count = additions + context
                    
                    # Create corrected header
                    corrected_header = f"@@ -{adjusted_old_start},{old_count} +{adjusted_new_start},{new_count} @@"
                    
                    # Preserve any context from original header
                    if '@@' in hunk_lines[0]:
                        parts = hunk_lines[0].split('@@')
                        if len(parts) >= 3:
                            corrected_header += f" {parts[2]}"
                    
                    hunk_lines[0] = corrected_header
                
                # Add corrected hunk
                # CRITICAL FIX: Don't filter out empty lines - they're significant in git patches
                for line in hunk_lines:
                    patch_parts.append(line)
        else:
            # Single hunk - use original logic with validation
            for hunk in sorted_hunks:
                hunk_lines = hunk.content.split('\n')
                
                # Validate hunk format
                if hunk_lines and hunk_lines[0].startswith('@@'):
                    hunk_header = hunk_lines[0]
                    if not _validate_hunk_header(hunk_header):
                        print(f"Warning: Invalid hunk header detected: {hunk_header}")
                        # Try to reconstruct a valid header
                        reconstructed_header = _reconstruct_hunk_header(hunk, hunk_lines)
                        if reconstructed_header:
                            hunk_lines[0] = reconstructed_header
                            print(f"✓ Reconstructed header: {reconstructed_header}")
                        else:
                            print(f"Error: Could not reconstruct valid header for hunk {hunk.id}, creating minimal fallback")
                            fallback_header = _create_fallback_header(hunk, hunk_lines)
                            hunk_lines[0] = fallback_header
                            print(f"✓ Created fallback header: {fallback_header}")
                
                # Add the hunk lines
                # CRITICAL FIX: Don't filter out empty lines - they're significant in git patches
                for line in hunk_lines:
                    patch_parts.append(line)
    
    return '\n'.join(patch_parts) + '\n' if patch_parts else ""


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


def analyze_hunk_change_type(hunk_content: str, file_path: str) -> str:
    """
    Analyze the type of change in a hunk to help with dependency detection.
    
    Args:
        hunk_content: The hunk content
        file_path: Path to the file being changed
        
    Returns:
        String describing the change type
    """
    lines = hunk_content.split('\n')
    
    # Check for import/export related changes
    import_patterns = [
        r'^\+.*import\s+.*from\s+[\'"]',  # ES6 imports
        r'^\+.*import\s+[\'"]',          # Import statements
        r'^\+.*require\s*\([\'"]',       # CommonJS require
        r'^\+.*from\s+[\'"].*[\'"]',     # From imports
    ]
    
    export_patterns = [
        r'^\+.*export\s+',               # Export statements
        r'^\+.*module\.exports\s*=',     # CommonJS exports
    ]
    
    # Count different types of changes
    additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    
    # Check for import/export changes
    for line in lines:
        for pattern in import_patterns:
            if re.match(pattern, line):
                return "import"
        for pattern in export_patterns:
            if re.match(pattern, line):
                return "export"
    
    # Determine change type based on addition/deletion ratio
    if deletions == 0 and additions > 0:
        return "addition"
    elif additions == 0 and deletions > 0:
        return "deletion"
    else:
        return "modification"


def analyze_hunk_dependencies(hunks: List[Hunk]) -> None:
    """
    Analyze dependencies between hunks to enable intelligent grouping.
    
    Args:
        hunks: List of hunks to analyze (modified in place)
    """
    # Build maps for quick lookups
    hunks_by_file = {}
    import_export_map = {}
    
    for hunk in hunks:
        if hunk.file_path not in hunks_by_file:
            hunks_by_file[hunk.file_path] = []
        hunks_by_file[hunk.file_path].append(hunk)
        
        # Extract import/export information
        if hunk.change_type in ["import", "export"]:
            imports, exports = extract_import_export_info(hunk.content)
            import_export_map[hunk.id] = {"imports": imports, "exports": exports}
    
    # Analyze dependencies
    for hunk in hunks:
        # 1. Import/Export dependencies
        if hunk.id in import_export_map:
            hunk_info = import_export_map[hunk.id]
            
            # Find dependencies based on what this hunk imports
            for imported_module in hunk_info["imports"]:
                for other_hunk in hunks:
                    if other_hunk.id != hunk.id and other_hunk.id in import_export_map:
                        other_info = import_export_map[other_hunk.id]
                        if imported_module in other_info["exports"]:
                            hunk.dependencies.add(other_hunk.id)
                            other_hunk.dependents.add(hunk.id)
        
        # 2. Line number dependencies (hunks that affect each other's line numbers)
        for other_hunk in hunks_by_file.get(hunk.file_path, []):
            if other_hunk.id != hunk.id:
                # Check if this hunk's line numbers depend on the other hunk
                if _hunks_have_line_dependencies(hunk, other_hunk):
                    if other_hunk.start_line < hunk.start_line:
                        # This hunk depends on the earlier hunk
                        hunk.dependencies.add(other_hunk.id)
                        other_hunk.dependents.add(hunk.id)
        
        # 3. Same file proximity dependencies (changes in the same file that are close together)
        for other_hunk in hunks_by_file.get(hunk.file_path, []):
            if other_hunk.id != hunk.id:
                # If hunks are very close (within 10 lines), they might be related
                line_distance = abs(hunk.start_line - other_hunk.start_line)
                if line_distance <= 10:
                    # Create weak dependencies for same-file proximity
                    if hunk.start_line > other_hunk.start_line:
                        hunk.dependencies.add(other_hunk.id)
                        other_hunk.dependents.add(hunk.id)
        
        # 4. Component usage dependencies (for frontend frameworks)
        if _is_frontend_file(hunk.file_path):
            component_deps = find_component_dependencies(hunk, hunks)
            for dep_id in component_deps:
                hunk.dependencies.add(dep_id)
                # Find the dependent hunk and update its dependents
                for other_hunk in hunks:
                    if other_hunk.id == dep_id:
                        other_hunk.dependents.add(hunk.id)
                        break


def extract_import_export_info(hunk_content: str) -> Tuple[Set[str], Set[str]]:
    """
    Extract import and export information from hunk content.
    
    Args:
        hunk_content: The hunk content to analyze
        
    Returns:
        Tuple of (imports, exports) as sets of module names
    """
    imports = set()
    exports = set()
    
    lines = hunk_content.split('\n')
    
    for line in lines:
        if not line.startswith('+'):
            continue
            
        line = line[1:].strip()  # Remove + prefix
        
        # Extract imports
        import_match = re.search(r'import\s+.*from\s+[\'"]([^\'"]+)[\'"]', line)
        if import_match:
            imports.add(import_match.group(1))
        
        import_match = re.search(r'import\s+[\'"]([^\'"]+)[\'"]', line)
        if import_match:
            imports.add(import_match.group(1))
        
        require_match = re.search(r'require\s*\([\'"]([^\'"]+)[\'"]\)', line)
        if require_match:
            imports.add(require_match.group(1))
        
        # Extract exports
        if 'export' in line:
            exports.add("__exported__")  # Simplified for now
    
    return imports, exports


def find_component_dependencies(hunk: Hunk, all_hunks: List[Hunk]) -> Set[str]:
    """
    Find component-related dependencies for frontend frameworks.
    
    Args:
        hunk: The hunk to analyze
        all_hunks: All hunks to search for dependencies
        
    Returns:
        Set of hunk IDs that this hunk depends on
    """
    dependencies = set()
    
    # Extract component names from the hunk content
    component_names = extract_component_names(hunk.content)
    
    # Look for hunks that define these components
    for other_hunk in all_hunks:
        if other_hunk.id != hunk.id:
            for component_name in component_names:
                if component_name in other_hunk.content:
                    dependencies.add(other_hunk.id)
                    break
    
    return dependencies


def extract_component_names(content: str) -> Set[str]:
    """
    Extract component names from content (simplified for now).
    
    Args:
        content: The content to analyze
        
    Returns:
        Set of component names found
    """
    component_names = set()
    
    # Simple patterns for common frontend frameworks
    patterns = [
        r'<(\w+)[^>]*>',           # HTML/JSX tags
        r'import\s+(\w+)\s+from',  # Import statements
        r'component\s*:\s*(\w+)',  # Vue component definitions
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if match and match[0].isupper():  # Component names typically start with uppercase
                component_names.add(match)
    
    return component_names


def _is_frontend_file(file_path: str) -> bool:
    """Check if a file is a frontend framework file."""
    frontend_extensions = ['.vue', '.svelte', '.jsx', '.tsx', '.js', '.ts']
    return any(file_path.endswith(ext) for ext in frontend_extensions)


def create_dependency_groups(hunks: List[Hunk]) -> List[List[Hunk]]:
    """
    Group hunks based on their dependencies for atomic application.
    
    Args:
        hunks: List of hunks with dependency information
        
    Returns:
        List of hunk groups that should be applied together
    """
    # Start with all hunks ungrouped
    ungrouped = set(hunk.id for hunk in hunks)
    hunk_map = {hunk.id: hunk for hunk in hunks}
    groups = []
    
    while ungrouped:
        # Start a new group with a hunk that has no ungrouped dependencies
        group_seeds = []
        for hunk_id in ungrouped:
            hunk = hunk_map[hunk_id]
            ungrouped_deps = hunk.dependencies & ungrouped
            if not ungrouped_deps:
                group_seeds.append(hunk_id)
        
        if not group_seeds:
            # If no seeds found, we have circular dependencies - break by picking the first one
            group_seeds = [next(iter(ungrouped))]
        
        # Build a group starting from a seed
        current_group = set()
        to_process = [group_seeds[0]]
        
        while to_process:
            current_id = to_process.pop(0)
            if current_id in ungrouped and current_id not in current_group:
                current_group.add(current_id)
                hunk = hunk_map[current_id]
                
                # Add all dependents that are still ungrouped
                for dependent_id in hunk.dependents:
                    if dependent_id in ungrouped and dependent_id not in current_group:
                        to_process.append(dependent_id)
                
                # Add dependencies that are still ungrouped
                for dep_id in hunk.dependencies:
                    if dep_id in ungrouped and dep_id not in current_group:
                        to_process.append(dep_id)
        
        # Convert group to list of hunks
        group_hunks = [hunk_map[hunk_id] for hunk_id in current_group]
        groups.append(group_hunks)
        
        # Remove grouped hunks from ungrouped
        ungrouped -= current_group
    
    return groups


def _validate_hunk_header(header: str) -> bool:
    """
    Validate that a hunk header has reasonable format.
    
    Args:
        header: The hunk header line starting with @@
        
    Returns:
        True if valid, False otherwise
    """
    match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
    if not match:
        return False
    
    old_start = int(match.group(1))
    old_count = int(match.group(2)) if match.group(2) else 1
    new_start = int(match.group(3))
    new_count = int(match.group(4)) if match.group(4) else 1
    
    # Basic sanity checks
    if old_start < 0 or new_start < 0:
        return False
    
    if old_count < 0 or new_count < 0:
        return False
    
    # Both counts can't be zero
    if old_count == 0 and new_count == 0:
        return False
    
    return True


def _reconstruct_hunk_header(hunk: Hunk, hunk_lines: List[str]) -> Optional[str]:
    """
    Try to reconstruct a valid hunk header from the hunk content with proper line number calculation.
    
    Args:
        hunk: The Hunk object
        hunk_lines: The lines of the hunk content
        
    Returns:
        Reconstructed header or None if unable
    """
    # Count additions and deletions
    additions = sum(1 for line in hunk_lines[1:] if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in hunk_lines[1:] if line.startswith('-') and not line.startswith('---'))
    context = sum(1 for line in hunk_lines[1:] if line.startswith(' '))
    
    # Calculate counts
    old_count = deletions + context
    new_count = additions + context
    
    # For proper git patches, we need to calculate line numbers that account for
    # the actual position in the CURRENT state, not the original diff state
    old_start = max(1, hunk.start_line)
    new_start = hunk.start_line
    
    # If we have sufficient context, adjust start positions
    if context > 0:
        context_offset = min(3, context // 2)  # Use up to 3 lines of leading context
        old_start = max(1, old_start - context_offset)
        new_start = max(1, new_start - context_offset)
    
    # Build header
    header = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
    
    # Extract any context from original header
    if hunk_lines and '@@' in hunk_lines[0]:
        parts = hunk_lines[0].split('@@')
        if len(parts) >= 3:
            header += f" {parts[2]}"
    
    return header


def _hunks_have_line_dependencies(hunk1: Hunk, hunk2: Hunk) -> bool:
    """
    Check if two hunks have line number dependencies.
    
    Args:
        hunk1: First hunk to check
        hunk2: Second hunk to check
        
    Returns:
        True if hunk1's line numbers depend on hunk2's changes
    """
    # Only check hunks in the same file
    if hunk1.file_path != hunk2.file_path:
        return False
    
    # Parse hunk headers to understand line number changes
    def get_line_changes(hunk_content: str) -> Tuple[int, int]:
        """Extract line changes (additions, deletions) from hunk content."""
        lines = hunk_content.split('\n')
        additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
        return additions, deletions
    
    # Get line changes for both hunks
    adds1, dels1 = get_line_changes(hunk1.content)
    adds2, dels2 = get_line_changes(hunk2.content)
    
    # Calculate net line change (positive = file grows, negative = file shrinks)
    net_change2 = adds2 - dels2
    
    # If hunk2 changes the file size and comes before hunk1,
    # then hunk1's line numbers are affected by hunk2
    if hunk2.start_line < hunk1.start_line and net_change2 != 0:
        return True
    
    # Check for overlapping line ranges that would affect each other
    range1 = set(range(hunk1.start_line, hunk1.end_line + 1))
    range2 = set(range(hunk2.start_line, hunk2.end_line + 1))
    
    # If ranges overlap or are very close, they likely depend on each other
    if range1 & range2 or min(range1) - max(range2) <= 3 or min(range2) - max(range1) <= 3:
        return True
    
    return False


def _create_fallback_header(hunk: Hunk, hunk_lines: List[str]) -> str:
    """
    Create a minimal fallback header when reconstruction fails.
    
    Args:
        hunk: The Hunk object
        hunk_lines: The lines of the hunk content
        
    Returns:
        A minimal but valid header that git can apply
    """
    # Count actual content lines (exclude the bad header)
    content_lines = hunk_lines[1:] if len(hunk_lines) > 1 else []
    
    additions = sum(1 for line in content_lines if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in content_lines if line.startswith('-') and not line.startswith('---'))
    context = sum(1 for line in content_lines if line.startswith(' '))
    
    # For simple cases, create a minimal header
    if additions == 0 and deletions == 0:
        # No actual changes, just context - create a no-op header
        return f"@@ -{hunk.start_line},{context} +{hunk.start_line},{context} @@"
    
    # Calculate reasonable start positions
    old_start = max(1, hunk.start_line)
    new_start = max(1, hunk.start_line)
    
    old_count = deletions + context
    new_count = additions + context
    
    # Ensure counts are at least 1 if there are changes
    if old_count == 0 and (deletions > 0 or context > 0):
        old_count = 1
    if new_count == 0 and (additions > 0 or context > 0):
        new_count = 1
    
    return f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"


def _calculate_line_number_adjustments(hunks_for_file: List[Hunk]) -> Dict[str, Tuple[int, int]]:
    """
    Calculate line number adjustments for interdependent hunks in the same file.
    
    IMPORTANT: This function should only be called when hunks actually overlap.
    For non-overlapping hunks, the original line numbers are correct.
    
    Args:
        hunks_for_file: List of hunks affecting the same file
        
    Returns:
        Dictionary mapping hunk ID to (adjusted_old_start, adjusted_new_start)
    """
    # Sort hunks by original start line
    sorted_hunks = sorted(hunks_for_file, key=lambda h: h.start_line)
    
    adjustments = {}
    
    # For overlapping hunks, we need to be much more conservative
    # The key insight: only adjust line numbers if hunks actually interfere
    for i, hunk in enumerate(sorted_hunks):
        # Start with original line numbers - both old and new should start from the same base
        # since we're applying to the current state after reset to main
        adjusted_old_start = hunk.start_line
        adjusted_new_start = hunk.start_line
        
        # Apply cumulative shifts from all previous hunks that change file size
        cumulative_shift = 0
        for j in range(i):
            prev_hunk = sorted_hunks[j]
            
            # All previous hunks that change file size affect this hunk's line numbers
            additions, deletions = _count_hunk_changes(prev_hunk)
            hunk_net_change = additions - deletions
            
            # Only apply shift if there's an actual change and the previous hunk ends before this one
            if hunk_net_change != 0 and prev_hunk.end_line < hunk.start_line:
                cumulative_shift += hunk_net_change
        
        # Apply adjustment to new start position based on cumulative changes
        # The old_start stays at the original position for this hunk
        # The new_start gets adjusted based on all previous changes
        adjusted_new_start = max(1, hunk.start_line + cumulative_shift)
        
        adjustments[hunk.id] = (adjusted_old_start, adjusted_new_start)
    
    return adjustments


def _count_hunk_changes(hunk: Hunk) -> Tuple[int, int]:
    """
    Count additions and deletions in a hunk.
    
    Args:
        hunk: The hunk to analyze
        
    Returns:
        Tuple of (additions, deletions)
    """
    lines = hunk.content.split('\n')
    additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    return additions, deletions


def _create_valid_git_patch(hunks: List[Hunk], base_diff: str) -> str:
    """
    Create a valid git patch using original hunk content when possible.
    
    The key insight: hunks parsed from 'git diff main...HEAD' already have correct
    line numbers for application to the current state (after reset to main).
    We only need to recalculate line numbers when hunks actually overlap.
    
    Args:
        hunks: List of hunks to include
        base_diff: Original diff for header extraction
        
    Returns:
        Valid patch content for git apply
    """
    if not hunks:
        return ""
    
    # Group hunks by file
    hunks_by_file = {}
    for hunk in hunks:
        if hunk.file_path not in hunks_by_file:
            hunks_by_file[hunk.file_path] = []
        hunks_by_file[hunk.file_path].append(hunk)
    
    # Extract original file headers
    original_headers = _extract_original_headers(base_diff)
    
    patch_parts = []
    
    for file_path, file_hunks in hunks_by_file.items():
        # Add file header
        if file_path in original_headers:
            patch_parts.extend(original_headers[file_path])
        else:
            # Create fallback header
            patch_parts.extend([
                f"diff --git a/{file_path} b/{file_path}",
                f"index 0000000..1111111 100644",
                f"--- a/{file_path}",
                f"+++ b/{file_path}"
            ])
        
        # Sort hunks by start line
        sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
        
        # Check if hunks actually overlap and need line number recalculation
        needs_recalculation = _hunks_need_line_recalculation(sorted_hunks)
        
        if needs_recalculation:
            # Only recalculate line numbers for truly overlapping hunks
            adjustments = _calculate_line_number_adjustments(sorted_hunks)
            
            for hunk in sorted_hunks:
                adjusted_old_start, adjusted_new_start = adjustments[hunk.id]
                
                # Reconstruct hunk with adjusted line numbers
                hunk_lines = hunk.content.split('\n')
                
                if hunk_lines and hunk_lines[0].startswith('@@'):
                    # Count content for proper header
                    additions, deletions = _count_hunk_changes(hunk)
                    context = sum(1 for line in hunk_lines[1:] if line.startswith(' '))
                    
                    old_count = deletions + context
                    new_count = additions + context
                    
                    # Validate counts - git requires positive counts in most cases
                    # If count is 0, it usually means 1 line of context
                    if old_count == 0 and (deletions > 0 or additions > 0):
                        old_count = 1
                    if new_count == 0 and (deletions > 0 or additions > 0):
                        new_count = 1
                    
                    # Create corrected header
                    corrected_header = f"@@ -{adjusted_old_start},{old_count} +{adjusted_new_start},{new_count} @@"
                    
                    # Add context from original if present
                    if '@@' in hunk_lines[0]:
                        parts = hunk_lines[0].split('@@')
                        if len(parts) >= 3 and parts[2].strip():
                            corrected_header += f" {parts[2]}"
                    
                    # Validate the header format before using it
                    if _validate_hunk_header(corrected_header):
                        hunk_lines[0] = corrected_header
                    else:
                        # Fall back to reconstructing from scratch
                        fallback_header = _reconstruct_hunk_header(hunk, hunk_lines)
                        if fallback_header and _validate_hunk_header(fallback_header):
                            hunk_lines[0] = fallback_header
                        else:
                            print(f"Warning: Could not create valid header for hunk {hunk.id}, using original")
                            # Keep original header as last resort
                
                # Add corrected hunk to patch
                # CRITICAL FIX: Don't filter out empty lines - they're significant in git patches
                for line in hunk_lines:
                    patch_parts.append(line)
        else:
            # Use original hunk content without modification
            # This preserves the correct line numbers from the original diff
            for hunk in sorted_hunks:
                hunk_lines = hunk.content.split('\n')
                
                # Add original hunk content directly  
                # CRITICAL FIX: Don't filter out empty lines - they're significant in git patches
                for line in hunk_lines:
                    patch_parts.append(line)
    
    return '\n'.join(patch_parts) + '\n' if patch_parts else ""


def _hunks_need_line_recalculation(hunks: List[Hunk]) -> bool:
    """
    Determine if hunks in the same file need line number recalculation.
    
    We need to recalculate line numbers when:
    1. Hunks actually overlap
    2. Earlier hunks change the file size, affecting later hunks' line numbers
    
    Args:
        hunks: List of hunks in the same file, sorted by start_line
        
    Returns:
        True if hunks need line number recalculation, False if original can be used
    """
    if len(hunks) <= 1:
        return False
    
    # Check if any earlier hunk would affect later hunks' line numbers
    cumulative_change = 0
    
    for i in range(len(hunks)):
        current_hunk = hunks[i]
        
        # Check if this hunk directly overlaps with the next one
        if i < len(hunks) - 1:
            next_hunk = hunks[i + 1]
            # True overlap requires recalculation
            if current_hunk.end_line >= next_hunk.start_line:
                return True
        
        # Update cumulative change from this hunk
        additions, deletions = _count_hunk_changes(current_hunk)
        hunk_change = additions - deletions
        cumulative_change += hunk_change
        
        # If there's any cumulative change and more hunks to process,
        # we need to recalculate line numbers for subsequent hunks
        if cumulative_change != 0 and i < len(hunks) - 1:
            return True
    
    return False


def _extract_original_headers(base_diff: str) -> Dict[str, List[str]]:
    """
    Extract original file headers from the base diff.
    
    Args:
        base_diff: Original full diff output
        
    Returns:
        Dictionary mapping file paths to their header lines
    """
    headers = {}
    lines = base_diff.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        if line.startswith('diff --git'):
            # Extract file path
            match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if match:
                file_path = match.group(2)
                header_lines = [line]
                i += 1
                
                # Collect header lines until first @@
                while i < len(lines) and not lines[i].startswith('@@'):
                    if lines[i].startswith('diff --git'):
                        break
                    header_lines.append(lines[i])
                    i += 1
                
                headers[file_path] = header_lines
                continue
        i += 1
    
    return headers