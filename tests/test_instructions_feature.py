#!/usr/bin/env python3
"""
Test suite for the custom instructions feature in git-smart-squash.
Tests the --instructions CLI option and instructions config field.
"""

import unittest
import tempfile
import os
import sys
import yaml
import subprocess
from unittest.mock import patch, MagicMock, mock_open, call
import json

# Add the package to the path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .test_utils import timeout
from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, ConfigManager, AttributionConfig
from git_smart_squash.diff_parser import parse_diff, Hunk


class TestInstructionsFeature(unittest.TestCase):
    """Test the custom instructions feature."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cli = GitSmartSquashCLI()
        self.sample_diff = """diff --git a/src/api.py b/src/api.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/api.py
@@ -0,0 +1,10 @@
+def get_users():
+    return []
+
+def create_user(data):
+    pass
diff --git a/src/database.py b/src/database.py
new file mode 100644
index 0000000..2345678
--- /dev/null
+++ b/src/database.py
@@ -0,0 +1,5 @@
+def connect():
+    pass
+
+def query(sql):
+    pass
diff --git a/tests/test_api.py b/tests/test_api.py
new file mode 100644
index 0000000..3456789
--- /dev/null
+++ b/tests/test_api.py
@@ -0,0 +1,8 @@
+from src.api import get_users
+
+def test_get_users():
+    assert get_users() == []
"""

    @timeout(10)
    def test_cli_parser_accepts_instructions(self):
        """Test that the CLI parser accepts --instructions option."""
        parser = self.cli.create_parser()
        
        # Test short form
        args = parser.parse_args(['-i', 'Group by layer'])
        self.assertEqual(args.instructions, 'Group by layer')
        
        # Test long form
        args = parser.parse_args(['--instructions', 'Separate tests from implementation'])
        self.assertEqual(args.instructions, 'Separate tests from implementation')
        
        # Test with other options
        args = parser.parse_args(['--instructions', 'Custom rules', '--base', 'develop'])
        self.assertEqual(args.instructions, 'Custom rules')
        self.assertEqual(args.base, 'develop')
        
        # Test no instructions provided
        args = parser.parse_args([])
        self.assertIsNone(args.instructions)

    @timeout(10)
    def test_instructions_included_in_prompt(self):
        """Test that custom instructions are included in the AI prompt."""
        hunks = parse_diff(self.sample_diff)
        
        # Test with custom instructions
        prompt_with_instructions = self.cli._build_hunk_prompt(
            hunks, 
            "Group database changes separately from API changes"
        )
        
        self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt_with_instructions)
        self.assertIn("Group database changes separately from API changes", prompt_with_instructions)
        
        # Test without custom instructions
        prompt_without_instructions = self.cli._build_hunk_prompt(hunks)
        
        self.assertNotIn("CUSTOM INSTRUCTIONS FROM USER:", prompt_without_instructions)

    @timeout(10)
    def test_instructions_from_config_file(self):
        """Test that instructions can be loaded from config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            config_data = {
                'ai': {
                    'provider': 'openai',
                    'model': 'gpt-4.1',
                    'instructions': 'Always separate infrastructure changes'
                },
                'hunks': {
                    'show_hunk_context': True
                }
            }
            yaml.dump(config_data, f)
            config_file = f.name
        
        try:
            config_manager = ConfigManager()
            config = config_manager.load_config(config_file)
            
            self.assertEqual(config.ai.instructions, 'Always separate infrastructure changes')
            
        finally:
            os.unlink(config_file)

    @timeout(10)
    def test_cli_instructions_override_config(self):
        """Test that CLI instructions override config file instructions."""
        # Create a config with default instructions
        config = Config(
            ai=AIConfig(
                provider='openai',
                model='gpt-4.1',
                instructions='Default instructions from config'
            ),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False
        )
        
        self.cli.config = config
        
        # Mock args with CLI instructions
        mock_args = MagicMock()
        mock_args.instructions = 'Override instructions from CLI'
        mock_args.base = 'main'
        mock_args.auto_apply = False
        mock_args.no_attribution = False
        
        with patch.object(self.cli, 'get_full_diff') as mock_diff:
            mock_diff.return_value = self.sample_diff
            
            with patch.object(self.cli, 'analyze_with_ai') as mock_analyze:
                mock_analyze.return_value = [{'message': 'test', 'hunk_ids': [], 'rationale': 'test'}]
                
                with patch.object(self.cli, 'display_commit_plan'):
                    with patch.object(self.cli, 'get_user_confirmation', return_value=False):
                        self.cli.run_smart_squash(mock_args)
                
                # Verify that CLI instructions were used
                mock_analyze.assert_called_once()
                call_args = mock_analyze.call_args[0]
                self.assertEqual(call_args[2], 'Override instructions from CLI')

    @timeout(10)
    def test_instructions_passed_to_ai_provider(self):
        """Test that instructions are correctly passed through to AI provider."""
        config = Config(
            ai=AIConfig(provider='openai', model='gpt-4.1'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False
        )
        self.cli.config = config
        
        hunks = parse_diff(self.sample_diff)
        
        with patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate') as mock_generate:
            mock_generate.return_value = json.dumps([{
                'message': 'feat: add API endpoints',
                'hunk_ids': ['src/api.py:1-10'],
                'rationale': 'API implementation'
            }])
            
            result = self.cli.analyze_with_ai(
                hunks, 
                self.sample_diff,
                "Group by architectural layer"
            )
            
            # Verify generate was called
            mock_generate.assert_called_once()
            
            # Check that the prompt contains the instructions
            prompt = mock_generate.call_args[0][0]
            self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt)
            self.assertIn("Group by architectural layer", prompt)
            
            # Verify result
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['message'], 'feat: add API endpoints')

    @timeout(10)
    def test_empty_instructions_handling(self):
        """Test handling of empty or None instructions."""
        hunks = parse_diff(self.sample_diff)
        
        # Test with None
        prompt_none = self.cli._build_hunk_prompt(hunks, None)
        self.assertNotIn("CUSTOM INSTRUCTIONS FROM USER:", prompt_none)
        
        # Test with empty string
        prompt_empty = self.cli._build_hunk_prompt(hunks, "")
        self.assertNotIn("CUSTOM INSTRUCTIONS FROM USER:", prompt_empty)
        
        # Test with whitespace only
        prompt_whitespace = self.cli._build_hunk_prompt(hunks, "   ")
        self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt_whitespace)

    @timeout(10)
    def test_multiline_instructions(self):
        """Test that multiline instructions are properly handled."""
        hunks = parse_diff(self.sample_diff)
        
        multiline_instructions = """1. Group database migrations separately
2. Keep API endpoints in their own commit
3. Tests should be with their implementation"""
        
        prompt = self.cli._build_hunk_prompt(hunks, multiline_instructions)
        
        self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt)
        self.assertIn("Group database migrations separately", prompt)
        self.assertIn("Keep API endpoints in their own commit", prompt)
        self.assertIn("Tests should be with their implementation", prompt)

    @timeout(10)
    def test_special_characters_in_instructions(self):
        """Test that special characters in instructions are handled properly."""
        hunks = parse_diff(self.sample_diff)
        
        # Test with various special characters
        special_instructions = 'Use "feat:" for features & "fix:" for bugs (always!)'
        prompt = self.cli._build_hunk_prompt(hunks, special_instructions)
        
        self.assertIn(special_instructions, prompt)
        
        # Test with regex-like patterns
        regex_instructions = "Match pattern: \\[JIRA-\\d+\\]"
        prompt = self.cli._build_hunk_prompt(hunks, regex_instructions)
        
        self.assertIn(regex_instructions, prompt)

    @timeout(10)
    def test_instructions_with_examples(self):
        """Test instructions that include examples."""
        instructions_with_examples = """Group commits by feature area. For example:
- "feat(auth): add login functionality" 
- "feat(api): implement user endpoints"
- "test(auth): add login tests"
"""
        
        hunks = parse_diff(self.sample_diff)
        prompt = self.cli._build_hunk_prompt(hunks, instructions_with_examples)
        
        self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt)
        self.assertIn("Group commits by feature area", prompt)
        self.assertIn('feat(auth): add login functionality', prompt)

    @timeout(10)
    def test_integration_with_dry_run(self):
        """Test that instructions work correctly with --dry-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            # Initialize git repo
            subprocess.run(['git', 'init'], check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
            subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
            
            # Create initial commit
            with open('README.md', 'w') as f:
                f.write('# Test\n')
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
            
            # Create feature branch with changes
            subprocess.run(['git', 'checkout', '-b', 'feature'], check=True)
            
            with open('api.py', 'w') as f:
                f.write('def get_data():\n    return []\n')
            with open('db.py', 'w') as f:
                f.write('def connect():\n    pass\n')
            
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', 'WIP'], check=True)
            
            # Mock the AI response
            with patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate') as mock_generate:
                mock_generate.return_value = json.dumps([{
                    'message': 'feat: add database layer',
                    'hunk_ids': ['db.py:1-2'],
                    'rationale': 'Following instruction to separate layers'
                }, {
                    'message': 'feat: add API layer',
                    'hunk_ids': ['api.py:1-2'],
                    'rationale': 'Following instruction to separate layers'
                }])
                
                # Run with custom instructions
                parser = self.cli.create_parser()
                args = parser.parse_args([
                    '--instructions', 'Separate database and API layers'
                ])
                
                with patch('sys.stdout'):  # Suppress output
                    with patch.object(self.cli, 'get_user_confirmation', return_value=False):
                        self.cli.run_smart_squash(args)
                
                # Verify the AI was called with instructions
                mock_generate.assert_called_once()
                prompt = mock_generate.call_args[0][0]
                self.assertIn('Separate database and API layers', prompt)


class TestInstructionsEdgeCases(unittest.TestCase):
    """Test edge cases for the instructions feature."""
    
    @timeout(10)
    def test_very_long_instructions(self):
        """Test handling of very long instructions."""
        cli = GitSmartSquashCLI()
        
        # Create very long instructions (1000 characters)
        long_instructions = "Please follow these detailed rules: " + ("rule " * 200)
        
        hunks = parse_diff("diff --git a/test.py b/test.py\n+test")
        prompt = cli._build_hunk_prompt(hunks, long_instructions)
        
        self.assertIn("CUSTOM INSTRUCTIONS FROM USER:", prompt)
        self.assertIn(long_instructions, prompt)
        
    @timeout(10)
    def test_instructions_with_json_like_content(self):
        """Test instructions that contain JSON-like structures."""
        cli = GitSmartSquashCLI()
        
        json_instructions = 'Format commits like: {"type": "feat", "scope": "auth"}'
        
        hunks = parse_diff("diff --git a/test.py b/test.py\n+test")
        prompt = cli._build_hunk_prompt(hunks, json_instructions)
        
        self.assertIn(json_instructions, prompt)
        
    @timeout(10)
    def test_instructions_persistence_across_calls(self):
        """Test that instructions don't persist between different calls."""
        cli = GitSmartSquashCLI()
        hunks = parse_diff("diff --git a/test.py b/test.py\n+test")
        
        # First call with instructions
        prompt1 = cli._build_hunk_prompt(hunks, "First instruction set")
        self.assertIn("First instruction set", prompt1)
        
        # Second call without instructions
        prompt2 = cli._build_hunk_prompt(hunks)
        self.assertNotIn("First instruction set", prompt2)
        self.assertNotIn("CUSTOM INSTRUCTIONS FROM USER:", prompt2)
        
        # Third call with different instructions
        prompt3 = cli._build_hunk_prompt(hunks, "Different instructions")
        self.assertIn("Different instructions", prompt3)
        self.assertNotIn("First instruction set", prompt3)


if __name__ == '__main__':
    unittest.main()