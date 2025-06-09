# Hunk-Based Commit Organization Implementation Plan

## Overview
This plan outlines the conversion of git-smart-squash from organizing commits by files to organizing by individual hunks (change blocks). This will enable more granular and logical commit grouping.

## Implementation Steps

### 1. Create Diff Parser Module (`git_smart_squash/diff_parser.py`)
**Purpose**: Parse git diff output and extract individual hunks with unique identifiers.

**Key Components**:
- `Hunk` class with attributes:
  - `id`: Unique identifier (e.g., "file.py:123-145")
  - `file_path`: Path to the file
  - `start_line`: Starting line number
  - `end_line`: Ending line number
  - `content`: The actual diff content
  - `context`: Surrounding code context
- `parse_diff()` function to extract hunks from git diff output
- `get_hunk_context()` function to extract surrounding code for better AI understanding

**Example Structure**:
```python
@dataclass
class Hunk:
    id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    context: str
    
def parse_diff(diff_output: str) -> List[Hunk]:
    """Parse git diff output into individual hunks"""
    # Implementation here
```

### 2. Update AI Response Schemas
**File**: `git_smart_squash/ai/providers/simple_unified.py`

**Changes**:
- Replace `files` field with `hunk_ids` in commit group schema
- Update validation to work with hunk IDs instead of file paths
- Modify response parsing to handle hunk-based grouping

**Before**:
```json
{
  "commits": [{
    "subject": "...",
    "files": ["path/to/file.py", "another/file.js"]
  }]
}
```

**After**:
```json
{
  "commits": [{
    "subject": "...",
    "hunk_ids": ["file.py:123-145", "file.js:45-67", "file.py:200-210"]
  }]
}
```

### 3. Modify AI Prompt Generation
**File**: `git_smart_squash/ai/providers/simple_unified.py`

**Changes**:
- Update `_build_system_prompt()` to explain hunk-based organization
- Modify `_build_user_prompt()` to show individual hunks with IDs
- Include hunk context in prompts for better AI understanding

**Prompt Format**:
```
Analyze these code changes and group them into logical commits by hunk:

Hunk ID: file.py:123-145
File: src/module/file.py
Context: [class definition, method signatures]
Changes:
@@ -123,10 +123,15 @@ class MyClass:
+    def new_method(self):
+        """New functionality"""
+        return self.process()
...

Group related hunks together based on functionality, not just file location.
```

### 4. Create Hunk Applicator Module (`git_smart_squash/hunk_applicator.py`)
**Purpose**: Apply specific hunks to the git staging area.

**Key Functions**:
- `apply_hunks(hunk_ids: List[str])`: Stage specific hunks
- `create_patch_for_hunks(hunks: List[Hunk])`: Create patch file for selected hunks
- `validate_hunk_combination(hunks: List[Hunk])`: Ensure hunks can be applied together

**Implementation Strategy**:
- Use `git apply --cached` with custom patch files
- Handle conflicts when hunks overlap
- Provide fallback to file-based staging if needed

### 5. Update CLI Flow (`git_smart_squash/cli.py`)
**Changes to `squash_current_branch()` function**:

1. **Diff Collection**:
   ```python
   # Get the diff
   diff_output = subprocess.run(['git', 'diff', base_branch], ...)
   
   # Parse into hunks
   hunks = parse_diff(diff_output.stdout)
   ```

2. **AI Analysis**:
   ```python
   # Build prompt with hunks
   prompt = build_hunk_prompt(hunks)
   
   # Get AI grouping
   grouping = ai_provider.suggest_commit_groups(prompt)
   ```

3. **Commit Creation**:
   ```python
   for commit_group in grouping['commits']:
       # Reset to base
       subprocess.run(['git', 'reset', base_branch])
       
       # Apply specific hunks
       apply_hunks(commit_group['hunk_ids'])
       
       # Create commit
       subprocess.run(['git', 'commit', '-m', commit_group['subject']])
   ```

### 6. Update Display Logic
**Changes to `_display_commit_groups()` function**:

- Show hunks instead of files
- Display hunk context for user understanding
- Group hunks by file for readability

**Example Output**:
```
Commit 1: Add user authentication
  Hunks:
    - auth.py:45-89 (add login function)
    - auth.py:120-145 (add logout function)
    - models.py:23-45 (add User model)
    
Commit 2: Update documentation
  Hunks:
    - README.md:10-25 (update installation steps)
    - auth.py:1-15 (add module docstring)
```

### 7. Testing Strategy

#### Unit Tests
- Test diff parser with various diff formats
- Test hunk applicator with different scenarios
- Test AI response parsing with hunk IDs

#### Integration Tests (`test_functionality_comprehensive.py`)
- Test end-to-end flow with hunk-based grouping
- Test edge cases (overlapping hunks, conflicts)
- Test fallback mechanisms

#### Manual Testing Scenarios
1. Simple case: Multiple hunks in single file
2. Complex case: Interleaved hunks across files
3. Edge case: Hunks with dependencies
4. Error case: Conflicting hunks

### 8. Configuration Updates
**File**: `git_smart_squash/simple_config.py`

Add configuration options:
```python
# Hunk-based grouping settings  
'show_hunk_context': True,  # Include context in display
'context_lines': 3  # Number of context lines to show
```

### 9. Documentation Updates
- Update README.md with hunk-based examples
- Add section explaining benefits of hunk-based grouping
- Include troubleshooting guide for common issues

## Implementation Order
1. Create diff parser (can be tested independently)
2. Create hunk applicator (can be tested with mock data)
3. Update AI schemas and prompts
4. Integrate into CLI flow
5. Update display logic
6. Add configuration options
7. Comprehensive testing
8. Documentation updates

## Risk Mitigation
- **Risk**: Hunks may not apply cleanly when separated
  - **Mitigation**: Validate hunk combinations before applying
  
- **Risk**: AI may group hunks incorrectly
  - **Mitigation**: Show clear hunk descriptions, allow user override
  
- **Risk**: Performance with large diffs
  - **Mitigation**: Add pagination or hunk limits
  
- **Risk**: Binary files or non-text changes
  - **Mitigation**: Handle as single-file commits when hunk parsing fails

## Success Criteria
- [ ] Can parse any git diff into individual hunks
- [ ] AI correctly groups related hunks across files
- [ ] Hunks apply cleanly to create intended commits
- [ ] User can understand and verify hunk groupings
- [ ] Performance remains acceptable for large changes
- [ ] Graceful handling of binary files and unparseable diffs

## Estimated Timeline
- Diff parser: 2-3 hours
- Hunk applicator: 3-4 hours
- AI integration: 2-3 hours
- CLI updates: 2-3 hours
- Testing: 3-4 hours
- Documentation: 1-2 hours

**Total: 13-19 hours**

## Next Steps
1. Review and approve this plan
2. Create feature branch `feature/hunk-based-grouping`
3. Implement diff parser as first component
4. Proceed with implementation order above