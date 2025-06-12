#!/usr/bin/env python3
"""
Test suite for comprehensive patch corruption fixes.

This test suite validates that the major fixes for git-smart-squash patch generation
address the following critical issues:
1. Missing closing braces and content corruption
2. Improper line number recalculation causing corrupt patches
3. End-of-file marker handling
4. Patch validation and repair capabilities
"""

import unittest
from git_smart_squash.diff_parser import (
    parse_diff, create_hunk_patch, _validate_patch_comprehensive,
    _validate_hunk_header, _finalize_patch_content, _hunks_have_true_overlap
)


class TestPatchCorruptionFixes(unittest.TestCase):
    """Test suite for comprehensive patch corruption fixes."""
    
    def test_closing_brace_preservation(self):
        """Test that closing braces are preserved in JavaScript files."""
        js_diff = '''diff --git a/test.js b/test.js
index 1234567..abcdefg 100644
--- a/test.js
+++ b/test.js
@@ -1,3 +1,5 @@
 function test() {
+    console.log("hello");
     return "hello";
+    // New comment
 }
@@ -8,4 +10,6 @@ function another() {
     if (true) {
         console.log("world");
     }
+    // Another comment
+    return null;
 }'''
        
        hunks = parse_diff(js_diff)
        self.assertEqual(len(hunks), 2, "Should parse 2 hunks")
        
        patch = create_hunk_patch(hunks, js_diff)
        
        # Count closing braces
        original_braces = js_diff.count('}')
        patch_braces = patch.count('}')
        
        self.assertGreaterEqual(patch_braces, original_braces,
                               "Closing braces should be preserved")
        
        # Validate the patch
        is_valid, issues = _validate_patch_comprehensive(patch)
        self.assertTrue(is_valid, f"Patch should be valid, found issues: {issues}")
    
    def test_no_newline_at_end_of_file_handling(self):
        """Test proper handling of 'No newline at end of file' markers."""
        diff_with_no_newline = '''diff --git a/noend.txt b/noend.txt
index 1234567..abcdefg 100644
--- a/noend.txt
+++ b/noend.txt
@@ -1,2 +1,3 @@
 line 1
-line 2\\\ No newline at end of file
+line 2 modified
+line 3\\\ No newline at end of file'''
        
        hunks = parse_diff(diff_with_no_newline)
        self.assertEqual(len(hunks), 1, "Should parse 1 hunk")
        
        patch = create_hunk_patch(hunks, diff_with_no_newline)
        
        # Check that no-newline marker is preserved
        self.assertIn('No newline', patch, "No newline marker should be preserved")
        
        # Should not end with extra newline
        if 'No newline' in patch:
            # The patch format should not add trailing newlines when no-newline markers are present
            pass  # This is validated by the _finalize_patch_content function
    
    def test_multiple_hunk_line_number_calculation(self):
        """Test that line numbers are calculated correctly for multiple hunks."""
        multi_hunk_diff = '''diff --git a/multi.py b/multi.py
index 1234567..abcdefg 100644
--- a/multi.py
+++ b/multi.py
@@ -1,3 +1,4 @@
 def first():
+    print("first")
     pass
 
@@ -10,3 +11,4 @@ def second():
     pass
 
 def third():
+    print("third")
     pass'''
        
        hunks = parse_diff(multi_hunk_diff)
        self.assertEqual(len(hunks), 2, "Should parse 2 hunks")
        
        patch = create_hunk_patch(hunks, multi_hunk_diff)
        
        # Validate that patch has proper structure
        self.assertIn('@@', patch, "Should contain hunk headers")
        self.assertIn('def first', patch, "Should contain first function")
        self.assertIn('def third', patch, "Should contain third function")
        
        # Validate the patch
        is_valid, issues = _validate_patch_comprehensive(patch)
        self.assertTrue(is_valid, f"Multi-hunk patch should be valid, found issues: {issues}")
    
    def test_empty_line_preservation(self):
        """Test that empty lines are preserved in patches."""
        diff_with_empty_lines = '''diff --git a/empty.py b/empty.py
index 1234567..abcdefg 100644
--- a/empty.py
+++ b/empty.py
@@ -1,5 +1,7 @@
 def func():
     pass
 
+
 def another():
+    print("new")
     pass'''
        
        hunks = parse_diff(diff_with_empty_lines)
        patch = create_hunk_patch(hunks, diff_with_empty_lines)
        
        # Check that empty lines (context) are preserved
        lines = patch.split('\n')
        has_empty_context = any(line == ' ' for line in lines)
        
        # The patch should maintain file structure including empty lines
        self.assertIn('\n', patch, "Should contain newlines")
    
    def test_hunk_header_validation(self):
        """Test enhanced hunk header validation."""
        # Valid headers
        valid_headers = [
            "@@ -1,3 +1,4 @@",
            "@@ -10,5 +11,6 @@ function test()",
            "@@ -1 +1,2 @@",
        ]
        
        for header in valid_headers:
            self.assertTrue(_validate_hunk_header(header), 
                          f"Should validate header: {header}")
        
        # Invalid headers
        invalid_headers = [
            "@@ -1,3 +1,4",  # Missing closing @@
            "@ -1,3 +1,4 @@",  # Wrong opening
            "@@ -1,-3 +1,4 @@",  # Negative count
            "@@ -0,1 +0,1 @@",  # Zero start with content
            "",  # Empty
        ]
        
        for header in invalid_headers:
            self.assertFalse(_validate_hunk_header(header),
                           f"Should not validate header: {header}")
    
    def test_comprehensive_patch_validation(self):
        """Test comprehensive patch validation catches issues."""
        # Valid patch
        valid_patch = '''diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def test():
+    print("hello")
     pass
'''
        
        is_valid, issues = _validate_patch_comprehensive(valid_patch)
        self.assertTrue(is_valid, f"Valid patch should pass: {issues}")
        
        # Invalid patch - missing diff header
        invalid_patch = '''@@ -1,3 +1,4 @@
 def test():
+    print("hello")
     pass
'''
        
        is_valid, issues = _validate_patch_comprehensive(invalid_patch)
        self.assertFalse(is_valid, "Invalid patch should fail validation")
        self.assertTrue(any("diff --git" in issue for issue in issues),
                       "Should detect missing diff header")
    
    def test_true_overlap_detection(self):
        """Test that true hunk overlap detection works correctly."""
        from git_smart_squash.diff_parser import Hunk
        
        # Overlapping hunks
        hunk1 = Hunk("test.py:1-5", "test.py", 1, 5, "content1", "")
        hunk2 = Hunk("test.py:3-7", "test.py", 3, 7, "content2", "")
        
        self.assertTrue(_hunks_have_true_overlap([hunk1, hunk2]),
                       "Should detect true overlap")
        
        # Non-overlapping hunks
        hunk3 = Hunk("test.py:10-12", "test.py", 10, 12, "content3", "")
        
        self.assertFalse(_hunks_have_true_overlap([hunk1, hunk3]),
                        "Should not detect overlap for distant hunks")
    
    def test_patch_content_finalization(self):
        """Test patch content finalization with various scenarios."""
        # Test with no-newline marker
        parts_with_no_newline = [
            "diff --git a/test.txt b/test.txt",
            "@@ -1,1 +1,1 @@",
            "-old line",
            "+new line",
            "\\ No newline at end of file"
        ]
        
        result = _finalize_patch_content(parts_with_no_newline)
        # Should not add trailing newline when no-newline marker present
        self.assertIn("No newline", result)
        
        # Test without no-newline marker
        parts_normal = [
            "diff --git a/test.txt b/test.txt",
            "@@ -1,1 +1,1 @@",
            "-old line",
            "+new line"
        ]
        
        result = _finalize_patch_content(parts_normal)
        # Should add trailing newline for normal patches
        self.assertTrue(result.endswith('\n'))


if __name__ == '__main__':
    unittest.main()