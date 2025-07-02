"""Tests for dependency validation logic."""

import unittest
from git_smart_squash.dependency_validator import DependencyValidator, ValidationResult
from git_smart_squash.diff_parser import Hunk


class TestDependencyValidator(unittest.TestCase):
    """Test cases for DependencyValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = DependencyValidator()
    
    def test_valid_plan_no_dependencies(self):
        """Test validation passes when there are no dependencies."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h2", file_path="file2.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},
            {"hunk_ids": ["h2"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_valid_plan_dependencies_same_commit(self):
        """Test validation passes when dependent hunks are in the same commit."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file1.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        commits = [
            {"hunk_ids": ["h1", "h2"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_valid_plan_dependencies_earlier_commit(self):
        """Test validation passes when dependencies are in earlier commits."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h2", file_path="file1.py", start_line=10, end_line=15, 
                 content="", context="", dependencies={"h1"}),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},
            {"hunk_ids": ["h2"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_invalid_plan_dependency_in_later_commit(self):
        """Test validation fails when dependency is in a later commit."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file1.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},  # h1 depends on h2
            {"hunk_ids": ["h2"]},  # but h2 comes later
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("depends on", result.errors[0])
        self.assertIn("later commit", result.errors[0])
    
    def test_invalid_plan_missing_dependency(self):
        """Test validation fails when dependency is not in any commit."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("not in any commit", result.errors[0])
    
    def test_circular_dependencies_detected(self):
        """Test circular dependencies between commits are detected."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file1.py", start_line=10, end_line=15, 
                 content="", context="", dependencies={"h3"}),
            Hunk(id="h3", file_path="file1.py", start_line=20, end_line=25, 
                 content="", context="", dependencies={"h1"}),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},
            {"hunk_ids": ["h2"]},
            {"hunk_ids": ["h3"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertFalse(result.is_valid)
        # Should have both forward dependency errors and circular dependency error
        self.assertGreater(len(result.errors), 1)
        circular_error = any("Circular dependency" in error for error in result.errors)
        self.assertTrue(circular_error)
    
    def test_complex_valid_scenario(self):
        """Test a complex but valid scenario with multiple dependencies."""
        hunks = [
            Hunk(id="h1", file_path="base.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h2", file_path="base.py", start_line=10, end_line=15, 
                 content="", context="", dependencies={"h1"}),
            Hunk(id="h3", file_path="utils.py", start_line=1, end_line=5, 
                 content="", context=""),
            Hunk(id="h4", file_path="main.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h1", "h3"}),
        ]
        
        commits = [
            {"hunk_ids": ["h1", "h3"]},  # Base changes
            {"hunk_ids": ["h2", "h4"]},  # Dependent changes
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_suggest_fixes(self):
        """Test that fix suggestions are generated correctly."""
        hunks = [
            Hunk(id="h1", file_path="file1.py", start_line=1, end_line=5, 
                 content="", context="", dependencies={"h2"}),
            Hunk(id="h2", file_path="file1.py", start_line=10, end_line=15, 
                 content="", context=""),
        ]
        
        commits = [
            {"hunk_ids": ["h1"]},
            {"hunk_ids": ["h2"]},
        ]
        
        result = self.validator.validate_commit_plan(commits, hunks)
        suggestions = self.validator.suggest_fixes(result, commits)
        
        self.assertGreater(len(suggestions), 0)
        self.assertIn("merging commits", suggestions[0])
        self.assertIn("#1", suggestions[0])
        self.assertIn("#2", suggestions[0])


if __name__ == "__main__":
    unittest.main()