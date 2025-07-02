"""
Diff parser module for extracting individual hunks from git diff output.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict
from .logger import get_logger

logger = get_logger()


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
                        next_line.startswith('@@')):
                        break
                    elif (next_line.startswith('\\') and 'No newline' in next_line):
                        # CRITICAL FIX: Only include "No newline at end of file" markers if they're legitimate
                        # Validate that the previous line is actual content, not just part of malformed patch
                        if hunk_content_lines and len(hunk_content_lines) > 1:
                            prev_line = hunk_content_lines[-1]
                            # Check if previous line is actual file content (starts with +, -, or space)
                            if prev_line and len(prev_line) > 0 and prev_line[0] in ['+', '-', ' ']:
                                hunk_content_lines.append(next_line)
                                i += 1
                                break
                            else:
                                logger.debug(f"Skipping suspicious 'No newline' marker after non-content line: {prev_line}")
                                i += 1
                                break
                        else:
                            logger.debug(f"Skipping 'No newline' marker in hunk with insufficient content")
                            i += 1
                            break
                    else:
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
    Create a patch file containing only the specified hunks using ABSOLUTE MINIMAL modification.

    CRITICAL: This function now uses a completely different approach that NEVER modifies
    the original hunk content. It only extracts and reassembles hunks exactly as they
    appear in the original git diff output.

    Args:
        hunks: List of hunks to include in the patch
        base_diff: Original full diff output

    Returns:
        Patch content that can be applied with git apply
    """
    if not hunks:
        return ""

    # Use the absolutely minimal patch creation logic
    return _create_absolutely_minimal_patch(hunks, base_diff)


def _create_absolutely_minimal_patch(hunks: List[Hunk], base_diff: str) -> str:
    """
    ABSOLUTELY MINIMAL patch creation that NEVER modifies original content.

    This function works by:
    1. Finding the exact original hunk text in the base_diff
    2. Extracting it character-for-character without any modifications
    3. Reassembling with original file headers
    4. ZERO content modification, ZERO line number recalculation

    Args:
        hunks: List of hunks to include
        base_diff: Original diff to extract from

    Returns:
        Minimal patch that preserves all original content
    """
    if not hunks:
        return ""

    try:
        # Parse the base diff to extract original raw content
        original_hunks_map = _extract_original_hunks_raw(base_diff)
        original_headers = _extract_original_headers(base_diff)

        # Group hunks by file
        hunks_by_file = {}
        for hunk in hunks:
            if hunk.file_path not in hunks_by_file:
                hunks_by_file[hunk.file_path] = []
            hunks_by_file[hunk.file_path].append(hunk)

        # Build patch by direct reassembly
        patch_parts = []

        for file_path, file_hunks in hunks_by_file.items():
            # Add original file header
            if file_path in original_headers:
                patch_parts.extend(original_headers[file_path])
            else:
                # Absolute minimal fallback header
                patch_parts.extend([
                    f"diff --git a/{file_path} b/{file_path}",
                    f"--- a/{file_path}",
                    f"+++ b/{file_path}"
                ])

            # Add hunks in original order, using EXACT original content
            sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
            for hunk in sorted_hunks:
                # Use the EXACT original hunk content without ANY modifications
                if hunk.id in original_hunks_map:
                    original_content = original_hunks_map[hunk.id]
                    patch_parts.append(original_content)
                else:
                    # Fallback: use hunk content as-is (this should rarely happen)
                    patch_parts.append(hunk.content)

        # Assemble final patch with minimal processing
        result = '\n'.join(patch_parts)

        # Only add final newline if the patch doesn't already end with one
        if result and not result.endswith('\n'):
            result += '\n'

        return result

    except Exception as e:
        logger.error(f"Minimal patch creation failed: {e}")
        # Ultimate fallback - return empty patch rather than corrupted one
        return ""


def _extract_original_hunks_raw(base_diff: str) -> Dict[str, str]:
    """
    Extract the original hunk content exactly as it appears in the base diff.

    Args:
        base_diff: Original diff output

    Returns:
        Dictionary mapping hunk IDs to their exact original content
    """
    hunks_map = {}
    lines = base_diff.split('\n')
    i = 0
    current_file = None

    while i < len(lines):
        line = lines[i]

        # Track current file
        if line.startswith('diff --git'):
            match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if match:
                current_file = match.group(2)

        # Found a hunk header
        elif line.startswith('@@') and current_file:
            hunk_start = i
            hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if hunk_match:
                new_start = int(hunk_match.group(3))
                new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1

                # Calculate end line for hunk ID
                end_line = new_start + max(0, new_count - 1)
                hunk_id = f"{current_file}:{new_start}-{end_line}"

                # Extract the complete hunk content
                i += 1
                hunk_lines = [line]  # Start with the @@ line

                # Read until next hunk, file, or end
                while i < len(lines):
                    next_line = lines[i]
                    if (next_line.startswith('diff --git') or
                        next_line.startswith('@@')):
                        break

                    hunk_lines.append(next_line)
                    i += 1

                # Store the EXACT original content
                hunks_map[hunk_id] = '\n'.join(hunk_lines)
                continue

        i += 1

    return hunks_map












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
        # 1. Line number dependencies (hunks that affect each other's line numbers)
        for other_hunk in hunks_by_file.get(hunk.file_path, []):
            if other_hunk.id != hunk.id:
                # Check if this hunk's line numbers depend on the other hunk
                if _hunks_have_line_dependencies(hunk, other_hunk):
                    if other_hunk.start_line < hunk.start_line:
                        # This hunk depends on the earlier hunk
                        hunk.dependencies.add(other_hunk.id)
                        other_hunk.dependents.add(hunk.id)

        # 2. Same file proximity dependencies (changes in the same file that are close together)
        for other_hunk in hunks_by_file.get(hunk.file_path, []):
            if other_hunk.id != hunk.id:
                # If hunks are very close (within 10 lines), they might be related
                line_distance = abs(hunk.start_line - other_hunk.start_line)
                if line_distance <= 10:
                    # Create weak dependencies for same-file proximity
                    if hunk.start_line > other_hunk.start_line:
                        hunk.dependencies.add(other_hunk.id)
                        other_hunk.dependents.add(hunk.id)


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
    Enhanced validation for hunk headers with comprehensive checks.

    Args:
        header: The hunk header line starting with @@

    Returns:
        True if valid, False otherwise
    """
    if not header or not header.strip():
        return False

    # Must start and contain @@ markers
    if not header.startswith('@@') or header.count('@@') < 2:
        return False

    # Extract the core pattern
    match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
    if not match:
        return False

    try:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
    except (ValueError, TypeError):
        return False

    # Enhanced sanity checks
    if old_start < 0 or new_start < 0:
        return False

    if old_count < 0 or new_count < 0:
        return False

    # Both counts can't be zero except in very specific cases
    if old_count == 0 and new_count == 0:
        return False

    # Reasonable limits to prevent malformed headers
    if old_start > 1000000 or new_start > 1000000:
        return False

    if old_count > 10000 or new_count > 10000:
        return False

    # Line numbers should be reasonable
    if old_start == 0 and old_count > 0:
        return False  # Can't start at line 0 with content

    if new_start == 0 and new_count > 0:
        return False  # Can't start at line 0 with content

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

    ENHANCED: This function now uses much more conservative logic to prevent patch corruption.
    The key insight is that most hunks don't actually need line number adjustments
    because git diff already provides the correct line numbers for the current state.

    Args:
        hunks_for_file: List of hunks affecting the same file

    Returns:
        Dictionary mapping hunk ID to (adjusted_old_start, adjusted_new_start)
    """
    # Sort hunks by original start line
    sorted_hunks = sorted(hunks_for_file, key=lambda h: h.start_line)

    adjustments = {}

    # CRITICAL FIX: Use enhanced overlap detection
    # Only adjust if hunks have true content overlap
    if not _hunks_have_true_overlap(sorted_hunks):
        # No true overlap - use original line numbers
        for hunk in sorted_hunks:
            adjustments[hunk.id] = (hunk.start_line, hunk.start_line)
        return adjustments

    logger.warning(f"Detected true overlap between hunks, applying conservative adjustments...")

    # Apply minimal adjustments only when absolutely necessary
    for i, hunk in enumerate(sorted_hunks):
        # Start with original line numbers
        adjusted_old_start = hunk.start_line
        adjusted_new_start = hunk.start_line

        # Only adjust if there's a previous hunk that directly affects this one
        if i > 0:
            prev_hunk = sorted_hunks[i - 1]

            # Check for direct overlap requiring adjustment
            if prev_hunk.end_line >= hunk.start_line:
                # True overlap - calculate minimal safe adjustment
                additions, deletions = _count_hunk_changes(prev_hunk)
                net_change = additions - deletions

                # Apply minimal adjustment to avoid collision
                if net_change != 0:
                    # Conservative approach: adjust by minimum amount needed
                    adjusted_new_start = max(1, hunk.start_line + min(abs(net_change), 3))

                    # For deletions, also adjust old_start to avoid negative ranges
                    if net_change < 0:
                        adjusted_old_start = max(1, hunk.start_line - 1)

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
    Create a valid git patch using ABSOLUTELY MINIMAL modification approach.

    This now uses the completely rewritten minimal patch creation that NEVER
    modifies original hunk content.

    Args:
        hunks: List of hunks to include
        base_diff: Original diff for header extraction

    Returns:
        Valid patch content for git apply
    """
    return _create_absolutely_minimal_patch(hunks, base_diff)


def _validate_patch_format(patch_content: str) -> bool:
    """
    Validate that a patch has proper git patch format.

    Args:
        patch_content: The patch content to validate

    Returns:
        True if patch format is valid, False otherwise
    """
    if not patch_content.strip():
        return False

    lines = patch_content.split('\n')

    # Must start with diff header
    if not any(line.startswith('diff --git') for line in lines):
        return False

    # Must have proper hunk headers
    hunk_count = sum(1 for line in lines if line.startswith('@@'))
    if hunk_count == 0:
        return False

    # Check for malformed hunk headers
    for line in lines:
        if line.startswith('@@'):
            # Hunk header should match pattern: @@ -old_start,old_count +new_start,new_count @@
            if not line.count('@@') >= 2:
                return False
            if '-' not in line or '+' not in line:
                return False

    # Check for suspicious content patterns that could cause corruption
    for line in lines:
        # Empty lines at start of hunks can cause issues
        if line.startswith('@@') and lines.index(line) + 1 < len(lines):
            next_line = lines[lines.index(line) + 1]
            if next_line == '':
                logger.warning(f"Empty line immediately after hunk header: {line}")

    return True




def _attempt_patch_repair(patch_content: str, hunks: List[Hunk], base_diff: str) -> Optional[str]:
    """
    Attempt to repair a malformed patch by regenerating it from hunks.

    Args:
        patch_content: The malformed patch content
        hunks: The original hunks
        base_diff: The base diff for header extraction

    Returns:
        Repaired patch content or None if repair failed
    """
    try:
        logger.debug("Attempting to repair patch by regenerating from original hunks...")

        # Try to regenerate patch using simpler logic
        patch_parts = []

        # Group hunks by file
        hunks_by_file = {}
        for hunk in hunks:
            if hunk.file_path not in hunks_by_file:
                hunks_by_file[hunk.file_path] = []
            hunks_by_file[hunk.file_path].append(hunk)

        # Extract headers from base diff
        original_headers = _extract_original_headers(base_diff)

        for file_path, file_hunks in hunks_by_file.items():
            # Add file header
            if file_path in original_headers:
                patch_parts.extend(original_headers[file_path])
            else:
                # Minimal fallback header
                patch_parts.extend([
                    f"diff --git a/{file_path} b/{file_path}",
                    f"index 0000000..1111111 100644",
                    f"--- a/{file_path}",
                    f"+++ b/{file_path}"
                ])

            # Add hunks in original order without line number adjustments
            sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
            for hunk in sorted_hunks:
                hunk_lines = hunk.content.split('\n')
                # Use original hunk content without modifications
                for line in hunk_lines:
                    patch_parts.append(line)

        repaired_content = '\n'.join(patch_parts)

        # Only add newline if no "No newline at end of file" marker
        if repaired_content and not any('\\' in line and 'No newline' in line for line in patch_parts):
            repaired_content += '\n'

        # Validate the repair
        if _validate_patch_format_lenient(repaired_content):
            return repaired_content

        return None

    except Exception as e:
        logger.error(f"Patch repair failed: {e}")
        return None


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


def _hunks_have_true_overlap(hunks: List[Hunk]) -> bool:
    """
    Check if hunks have true content overlap that requires line number adjustment.

    This is more conservative than the existing overlap detection - only returns True
    if hunks actually interfere with each other's line ranges.

    Args:
        hunks: List of hunks to check (should be sorted by start_line)

    Returns:
        True if hunks have true overlap requiring adjustment
    """
    for i in range(len(hunks) - 1):
        current = hunks[i]
        next_hunk = hunks[i + 1]

        # True overlap: current hunk ends after next hunk starts
        if current.end_line >= next_hunk.start_line:
            return True

        # Check if current hunk changes file size significantly
        # and would affect next hunk's line numbers
        additions, deletions = _count_hunk_changes(current)
        net_change = additions - deletions

        # If there's a significant net change and hunks are close together
        if abs(net_change) > 0 and (next_hunk.start_line - current.end_line) <= 3:
            return True

    return False


def _carefully_adjust_hunk_line_numbers(hunk: Hunk, all_hunks: List[Hunk], hunk_index: int) -> Optional[str]:
    """
    Carefully adjust line numbers for a hunk only when absolutely necessary.

    This function uses conservative logic to minimize the risk of corruption.

    Args:
        hunk: The hunk to adjust
        all_hunks: All hunks in the file (sorted)
        hunk_index: Index of current hunk in all_hunks

    Returns:
        Adjusted hunk content or None if no adjustment needed
    """
    hunk_lines = hunk.content.split('\n')
    if not hunk_lines or not hunk_lines[0].startswith('@@'):
        return None

    # Calculate cumulative line offset from previous hunks
    cumulative_offset = 0
    for i in range(hunk_index):
        prev_hunk = all_hunks[i]
        additions, deletions = _count_hunk_changes(prev_hunk)
        net_change = additions - deletions

        # Only apply offset if previous hunk actually affects this one
        if prev_hunk.end_line < hunk.start_line:
            cumulative_offset += net_change

    # If no meaningful offset, don't adjust
    if abs(cumulative_offset) == 0:
        return None

    # Parse original header
    header_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', hunk_lines[0])
    if not header_match:
        return None

    old_start = int(header_match.group(1))
    old_count = int(header_match.group(2)) if header_match.group(2) else 1
    new_start = int(header_match.group(3))
    new_count = int(header_match.group(4)) if header_match.group(4) else 1
    context = header_match.group(5) or ""

    # Apply conservative adjustment
    adjusted_new_start = max(1, new_start + cumulative_offset)

    # Create new header
    new_header = f"@@ -{old_start},{old_count} +{adjusted_new_start},{new_count} @@{context}"

    # Validate the new header before returning
    if _validate_hunk_header(new_header):
        hunk_lines[0] = new_header
        return '\n'.join(hunk_lines)

    return None


def _repair_hunk_header_conservative(hunk: Hunk, hunk_lines: List[str]) -> Optional[str]:
    """
    Conservatively repair a malformed hunk header.

    Args:
        hunk: The hunk object
        hunk_lines: Lines of hunk content

    Returns:
        Repaired header or None if repair not possible
    """
    if len(hunk_lines) < 2:
        return None

    # Count actual changes in hunk content
    additions = sum(1 for line in hunk_lines[1:] if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in hunk_lines[1:] if line.startswith('-') and not line.startswith('---'))
    context = sum(1 for line in hunk_lines[1:] if line.startswith(' '))

    # Use hunk object's line numbers as base
    old_start = max(1, hunk.start_line)
    new_start = max(1, hunk.start_line)

    old_count = deletions + context
    new_count = additions + context

    # Ensure counts are at least 1 if there are any changes
    if old_count == 0 and (deletions > 0 or context > 0):
        old_count = 1
    if new_count == 0 and (additions > 0 or context > 0):
        new_count = 1

    # Create conservative header
    repaired = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"

    # Extract any function context from original header if possible
    if len(hunk_lines) > 0 and '@@' in hunk_lines[0]:
        parts = hunk_lines[0].split('@@')
        if len(parts) >= 3 and parts[2].strip():
            repaired += f" {parts[2]}"

    return repaired if _validate_hunk_header(repaired) else None


def _finalize_patch_content(patch_parts: List[str]) -> str:
    """
    Finalize patch content with enhanced end-of-file handling.

    This function properly handles "No newline at end of file" markers and ensures
    the patch maintains the correct file ending state.

    Args:
        patch_parts: List of patch lines

    Returns:
        Finalized patch content
    """
    if not patch_parts:
        return ""

    # CRITICAL FIX: Enhanced "No newline at end of file" detection with validation
    has_no_newline_marker = False
    no_newline_positions = []
    valid_no_newline_markers = []

    for i, line in enumerate(patch_parts):
        if line.startswith('\\') and 'No newline' in line:
            has_no_newline_marker = True
            no_newline_positions.append(i)

            # CRITICAL FIX: Validate that the "No newline" marker is legitimate
            # It should only appear after actual file content lines, not be artificially added
            if i > 0:
                prev_line = patch_parts[i - 1]
                # Check if previous line is actual content (starts with +, -, or space)
                if prev_line and len(prev_line) > 0 and prev_line[0] in ['+', '-', ' ']:
                    valid_no_newline_markers.append(i)
                else:
                    logger.warning(f"Suspicious 'No newline' marker at position {i} after non-content line: {prev_line}")

    # CRITICAL FIX: Only preserve "No newline" markers that are actually valid
    if valid_no_newline_markers:
        logger.debug(f"Preserving valid 'No newline at end of file' state (found {len(valid_no_newline_markers)} valid markers)")
        # Join parts with newlines, preserving the no-newline markers
        patch_content = '\n'.join(patch_parts)
    else:
        # No valid "no newline" markers - filter out any invalid ones
        if has_no_newline_marker and not valid_no_newline_markers:
            logger.debug(f"Filtering out {len(no_newline_positions)} invalid 'No newline' markers")
            cleaned_parts = [part for i, part in enumerate(patch_parts)
                           if not (part.startswith('\\') and 'No newline' in part)]
            patch_content = '\n'.join(cleaned_parts)
        else:
            patch_content = '\n'.join(patch_parts)

        # Add trailing newline for standard git patch format
        if patch_content and not patch_content.endswith('\n'):
            patch_content += '\n'

    return patch_content


def _validate_patch_comprehensive(patch_content: str) -> Tuple[bool, List[str]]:
    """
    Comprehensive patch validation that detects various corruption patterns.

    Args:
        patch_content: Patch content to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    if not patch_content or not patch_content.strip():
        issues.append("Patch content is empty")
        return False, issues

    lines = patch_content.split('\n')

    # Check for basic patch structure
    has_diff_header = any(line.startswith('diff --git') for line in lines)
    has_hunk_header = any(line.startswith('@@') for line in lines)

    if not has_diff_header:
        issues.append("Missing 'diff --git' header")

    if not has_hunk_header:
        issues.append("Missing hunk headers '@@'")

    # Validate each hunk header
    for i, line in enumerate(lines):
        if line.startswith('@@'):
            if not _validate_hunk_header(line):
                issues.append(f"Invalid hunk header at line {i+1}: {line}")

    # Check for content corruption patterns
    for i, line in enumerate(lines):
        # Check for truncated lines that might indicate corruption
        if line.endswith('\\'):
            if i == len(lines) - 1 or not lines[i + 1].startswith('No newline'):
                issues.append(f"Suspicious line ending with backslash at line {i+1}")

        # Check for malformed diff lines
        if len(line) > 0:
            first_char = line[0]
            if first_char in ['+', '-', ' ']:
                # Check for common corruption patterns in diff content
                if line == '+' or line == '-' or line == ' ':
                    # Empty addition/deletion/context line might be intentional
                    continue

                # ENHANCED: Check for lines that seem cut off (missing closing braces in code)
                if first_char in ['+', '-']:
                    content = line[1:]
                    # More conservative check - only flag if there's a clear pattern
                    if content.strip().endswith('{'):
                        # Look ahead for matching closing brace in reasonable range
                        has_matching_brace = False
                        for j in range(i+1, min(i+10, len(lines))):
                            if j < len(lines) and '}' in lines[j]:
                                has_matching_brace = True
                                break
                        if not has_matching_brace:
                            # Also check if this is end of a file that should have closing brace
                            is_near_end = i >= len(lines) - 3
                            if is_near_end:
                                issues.append(f"Potential missing closing brace near end of file at line {i+1}")
                            else:
                                issues.append(f"Potential missing closing brace near line {i+1}")

                    # NEW: Check for files that end abruptly without proper closure
                    if i == len(lines) - 1 or (i == len(lines) - 2 and lines[i+1].startswith('\\')):
                        # This is the last content line, check if it needs a closing brace
                        stripped_content = content.strip()
                        if stripped_content and not stripped_content.endswith(('}', ';', ')', ']')):
                            # Check if this looks like it should end with a brace
                            if any(keyword in stripped_content.lower() for keyword in ['function', 'if', 'for', 'while', 'class']):
                                issues.append(f"File may end abruptly without proper closure at line {i+1}")

                # NEW: Validate "No newline at end of file" markers
                if line.startswith('\\') and 'No newline' in line:
                    if i == 0 or not lines[i-1]:
                        issues.append(f"Invalid 'No newline' marker at line {i+1} - no preceding content")
                    elif i > 0:
                        prev_line = lines[i-1]
                        if not (len(prev_line) > 0 and prev_line[0] in ['+', '-', ' ']):
                            issues.append(f"Invalid 'No newline' marker at line {i+1} - previous line is not content")

    # Check for mismatched file headers and hunks
    current_file = None
    hunks_for_current_file = 0

    for line in lines:
        if line.startswith('diff --git'):
            if current_file and hunks_for_current_file == 0:
                issues.append(f"File {current_file} has header but no hunks")

            # Extract new file
            match = re.match(r'diff --git a/(.*) b/(.*)', line)
            if match:
                current_file = match.group(2)
                hunks_for_current_file = 0
            else:
                issues.append(f"Malformed diff header: {line}")
        elif line.startswith('@@'):
            hunks_for_current_file += 1

    # Check final file
    if current_file and hunks_for_current_file == 0:
        issues.append(f"File {current_file} has header but no hunks")

    return len(issues) == 0, issues




def _repair_patch_conservative(patch_content: str, hunks: List[Hunk], base_diff: str) -> Optional[str]:
    """
    Attempt conservative patch repair by regenerating from original hunks.

    Args:
        patch_content: Malformed patch content
        hunks: Original hunks
        base_diff: Base diff for headers

    Returns:
        Repaired patch or None if repair failed
    """
    try:
        # Regenerate patch using simple logic - just use original hunk content
        patch_parts = []

        # Group hunks by file
        hunks_by_file = {}
        for hunk in hunks:
            if hunk.file_path not in hunks_by_file:
                hunks_by_file[hunk.file_path] = []
            hunks_by_file[hunk.file_path].append(hunk)

        # Extract headers
        original_headers = _extract_original_headers(base_diff)

        for file_path, file_hunks in hunks_by_file.items():
            # Add file header
            if file_path in original_headers:
                patch_parts.extend(original_headers[file_path])
            else:
                patch_parts.extend([
                    f"diff --git a/{file_path} b/{file_path}",
                    f"index 0000000..1111111 100644",
                    f"--- a/{file_path}",
                    f"+++ b/{file_path}"
                ])

            # Add hunks with validation for "No newline" markers
            sorted_hunks = sorted(file_hunks, key=lambda h: h.start_line)
            for hunk in sorted_hunks:
                hunk_lines = hunk.content.split('\n')
                for j, line in enumerate(hunk_lines):
                    # CRITICAL FIX: Filter out invalid "No newline" markers during repair
                    if line.startswith('\\') and 'No newline' in line:
                        # Only include if previous line is actual content
                        if j > 0 and hunk_lines[j-1] and len(hunk_lines[j-1]) > 0 and hunk_lines[j-1][0] in ['+', '-', ' ']:
                            patch_parts.append(line)
                        else:
                            logger.debug(f"Filtering out invalid 'No newline' marker during repair: {line}")
                    else:
                        patch_parts.append(line)

        # Finalize repaired content
        repaired = _finalize_patch_content(patch_parts)

        # Validate repair
        if _validate_patch_conservative(repaired):
            return repaired

        return None

    except Exception as e:
        logger.error(f"Patch repair failed: {e}")
        return None
