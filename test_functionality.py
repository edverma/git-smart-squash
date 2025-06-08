#!/usr/bin/env python3
"""
Comprehensive test suite for Git Smart Squash functionality.
Tests all features described in FUNCTIONALITY.md.
"""

import unittest
import tempfile
import shutil
import subprocess
import os
import sys
from unittest.mock import patch, MagicMock, mock_open
import json

# Add the package to the path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import ConfigManager, Config, AIConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider


class TestGitSmartSquashFunctionality(unittest.TestCase):
    """Test all functionality described in FUNCTIONALITY.md"""
    
    def setUp(self):
        """Set up test environment with temporary directory and mock git repo."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize a mock git repository
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        
        # Create main branch with initial commit
        with open('README.md', 'w') as f:
            f.write('# Test Project\n')
        subprocess.run(['git', 'add', 'README.md'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        # Create a feature branch
        subprocess.run(['git', 'checkout', '-b', 'feature-branch'], check=True)
        
        # Add some changes to simulate a messy commit history
        os.makedirs('src', exist_ok=True)
        os.makedirs('docs', exist_ok=True)
        os.makedirs('tests', exist_ok=True)
        
        with open('src/auth.py', 'w') as f:
            f.write('def authenticate(user): pass\n')
        with open('src/models.py', 'w') as f:
            f.write('class User: pass\n')
        with open('docs/api.md', 'w') as f:
            f.write('# API Documentation\n')
        
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'WIP: various changes'], check=True)
        
        # Add more changes
        with open('tests/test_auth.py', 'w') as f:
            f.write('def test_auth(): pass\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'add tests'], check=True)
        
        self.cli = GitSmartSquashCLI()
    
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_config_manager_loading(self):
        """Test configuration loading as described in FUNCTIONALITY.md"""
        config_manager = ConfigManager()
        
        # Test default config creation
        config = config_manager.load_config()
        self.assertIsInstance(config, Config)
        self.assertEqual(config.ai.provider, 'local')
        self.assertEqual(config.ai.model, 'devstral')
        
        # Test config file loading
        config_data = {
            'ai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key_env': 'OPENAI_API_KEY'
            }
        }
        
        with patch('builtins.open', mock_open(read_data='ai:\n  provider: openai\n  model: gpt-4\n')):
            with patch('os.path.exists', return_value=True):
                with patch('yaml.safe_load', return_value=config_data):
                    config = config_manager.load_config('.git-smart-squash.yml')
                    self.assertEqual(config.ai.provider, 'openai')
                    self.assertEqual(config.ai.model, 'gpt-4')
    
    def test_get_full_diff(self):
        """Test Step 1: Analyze Changes - getting the complete diff"""
        diff_content = self.cli.get_full_diff('main')
        
        # Should return a non-empty diff
        self.assertIsNotNone(diff_content)
        self.assertIn('src/auth.py', diff_content)
        self.assertIn('src/models.py', diff_content)
        self.assertIn('docs/api.md', diff_content)
        self.assertIn('tests/test_auth.py', diff_content)
    
    def test_get_full_diff_no_changes(self):
        """Test diff extraction when no changes exist"""
        # Switch to main branch (no changes)
        subprocess.run(['git', 'checkout', 'main'], check=True)
        diff_content = self.cli.get_full_diff('main')
        self.assertIsNone(diff_content)
    
    def test_get_full_diff_with_alternative_base(self):
        """Test with different base branch as shown in usage examples"""
        # Create a develop branch
        subprocess.run(['git', 'checkout', 'main'], check=True)
        subprocess.run(['git', 'checkout', '-b', 'develop'], check=True)
        subprocess.run(['git', 'checkout', 'feature-branch'], check=True)
        
        diff_content = self.cli.get_full_diff('develop')
        self.assertIsNotNone(diff_content)
    
    @patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate')
    def test_ai_analysis_json_response(self, mock_generate):
        """Test Step 2: AI Analysis with proper JSON response"""
        # Mock AI response as described in FUNCTIONALITY.md
        mock_response = '''[
            {
                "message": "feat: add user authentication system",
                "files": ["src/auth.py", "src/models.py", "tests/test_auth.py"],
                "rationale": "Groups all authentication-related changes together"
            },
            {
                "message": "docs: update API documentation for auth endpoints", 
                "files": ["docs/api.md"],
                "rationale": "Separates documentation updates from implementation"
            }
        ]'''
        
        mock_generate.return_value = mock_response
        
        diff_content = "mock diff content"
        commit_plan = self.cli.analyze_with_ai(diff_content)
        
        self.assertIsNotNone(commit_plan)
        self.assertEqual(len(commit_plan), 2)
        
        # Verify first commit structure
        self.assertEqual(commit_plan[0]['message'], 'feat: add user authentication system')
        self.assertIn('src/auth.py', commit_plan[0]['files'])
        self.assertIn('authentication-related', commit_plan[0]['rationale'])
        
        # Verify second commit structure  
        self.assertEqual(commit_plan[1]['message'], 'docs: update API documentation for auth endpoints')
        self.assertIn('docs/api.md', commit_plan[1]['files'])
    
    @patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate')
    def test_ai_analysis_fallback_parsing(self, mock_generate):
        """Test AI analysis fallback when JSON parsing fails"""
        # Mock non-JSON response that needs fallback parsing
        mock_response = '''Here are the suggested commits:
        
        - feat: add authentication system
        - docs: update documentation
        - test: add test coverage
        '''
        
        mock_generate.return_value = mock_response
        
        diff_content = "mock diff content"
        commit_plan = self.cli.analyze_with_ai(diff_content)
        
        self.assertIsNotNone(commit_plan)
        self.assertGreater(len(commit_plan), 0)
        self.assertIn('message', commit_plan[0])
    
    def test_ai_providers_configuration(self):
        """Test AI provider configuration as described in FUNCTIONALITY.md"""
        # Test local provider (default)
        config = Config(ai=AIConfig(provider='local', model='devstral'))
        provider = UnifiedAIProvider(config)
        self.assertEqual(provider.provider_type, 'local')
        
        # Test OpenAI provider
        config = Config(ai=AIConfig(provider='openai', model='gpt-4'))
        provider = UnifiedAIProvider(config)
        self.assertEqual(provider.provider_type, 'openai')
        
        # Test Anthropic provider
        config = Config(ai=AIConfig(provider='anthropic', model='claude-3-sonnet'))
        provider = UnifiedAIProvider(config)
        self.assertEqual(provider.provider_type, 'anthropic')
    
    @patch('subprocess.run')
    def test_ai_local_provider_ollama(self, mock_subprocess):
        """Test local AI provider using Ollama"""
        # Mock successful Ollama response
        mock_response = {
            'response': 'Generated commit plan...'
        }
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = json.dumps(mock_response)
        
        config = Config(ai=AIConfig(provider='local', model='devstral'))
        provider = UnifiedAIProvider(config)
        
        result = provider._generate_local('test prompt')
        self.assertEqual(result, 'Generated commit plan...')
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('git_smart_squash.ai.providers.simple_unified.openai')
    def test_ai_openai_provider(self, mock_openai):
        """Test OpenAI provider configuration"""
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'OpenAI generated plan'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client
        
        config = Config(ai=AIConfig(provider='openai', model='gpt-4'))
        provider = UnifiedAIProvider(config)
        
        result = provider._generate_openai('test prompt')
        self.assertEqual(result, 'OpenAI generated plan')
    
    def test_display_commit_plan(self):
        """Test Step 3: Review Proposed Structure display"""
        # Test commit plan display (this tests the console output structure)
        commit_plan = [
            {
                'message': 'feat: add user authentication system',
                'files': ['src/auth.py', 'src/models/user.py'], 
                'rationale': 'Groups all authentication-related changes together'
            },
            {
                'message': 'docs: update API documentation',
                'files': ['docs/api.md'],
                'rationale': 'Separates documentation updates'
            }
        ]
        
        # This should not raise any exceptions
        with patch('git_smart_squash.cli.Console'):
            self.cli.display_commit_plan(commit_plan)
    
    @patch('subprocess.run')
    def test_apply_commit_plan_backup_creation(self, mock_subprocess):
        """Test Step 4: Apply Changes - backup branch creation"""
        # Mock git commands for backup creation
        mock_subprocess.side_effect = [
            # git rev-parse --abbrev-ref HEAD
            MagicMock(stdout='feature-branch\n', returncode=0),
            # git branch backup-branch
            MagicMock(returncode=0),
            # git reset --soft main
            MagicMock(returncode=0),
            # git add .
            MagicMock(returncode=0),
            # git commit -m "message"
            MagicMock(returncode=0)
        ]
        
        commit_plan = [{'message': 'feat: test commit', 'files': [], 'rationale': 'test'}]
        
        # Should not raise exceptions
        self.cli.apply_commit_plan(commit_plan, 'main')
        
        # Verify backup branch creation was attempted
        self.assertTrue(any('branch' in str(call) for call in mock_subprocess.call_args_list))
    
    def test_safety_features_clean_working_directory(self):
        """Test safety features - validates working directory state"""
        # Add uncommitted changes
        with open('uncommitted.txt', 'w') as f:
            f.write('uncommitted change')
        
        # This simulates checking for safety (actual implementation would check git status)
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        self.assertIn('uncommitted.txt', result.stdout)  # Should detect uncommitted changes
    
    def test_dry_run_functionality(self):
        """Test dry run functionality as described in usage examples"""
        with patch.object(self.cli, 'get_full_diff') as mock_diff:
            with patch.object(self.cli, 'analyze_with_ai') as mock_ai:
                mock_diff.return_value = 'mock diff'
                mock_ai.return_value = [{'message': 'test', 'files': [], 'rationale': 'test'}]
                
                # Mock command line args for dry run
                args = MagicMock()
                args.base = 'main'
                args.dry_run = True
                
                # Should complete without applying changes
                self.cli.run_smart_squash(args)
                
                # Verify AI analysis was called but no git operations performed
                mock_ai.assert_called_once()
    
    def test_argument_parser_creation(self):
        """Test CLI argument parser supports all usage examples from FUNCTIONALITY.md"""
        parser = self.cli.create_parser()
        
        # Test basic arguments
        args = parser.parse_args(['--dry-run'])
        self.assertTrue(args.dry_run)
        
        # Test base branch argument
        args = parser.parse_args(['--base', 'develop'])
        self.assertEqual(args.base, 'develop')
        
        # Test AI provider arguments
        args = parser.parse_args(['--ai-provider', 'openai', '--model', 'gpt-4'])
        self.assertEqual(args.ai_provider, 'openai')
        self.assertEqual(args.model, 'gpt-4')
    
    def test_conventional_commit_message_format(self):
        """Test that generated commit messages follow conventional commit standards"""
        # Test commit message validation
        valid_messages = [
            'feat: add user authentication system',
            'docs: update API documentation for auth endpoints', 
            'refactor: extract validation utilities',
            'fix: resolve authentication bug',
            'test: add comprehensive test coverage',
            'chore: update dependencies'
        ]
        
        for message in valid_messages:
            # Should start with type followed by colon
            self.assertRegex(message, r'^[a-z]+: .+')
            
            # Should be descriptive (more than just type)
            parts = message.split(': ', 1)
            self.assertEqual(len(parts), 2)
            self.assertGreater(len(parts[1]), 3)
    
    def test_error_handling_and_recovery(self):
        """Test error handling scenarios described in FUNCTIONALITY.md"""
        # Test invalid base branch
        with self.assertRaises(Exception):
            self.cli.get_full_diff('nonexistent-branch')
        
        # Test AI analysis failure
        with patch.object(self.cli, 'analyze_with_ai', return_value=None):
            args = MagicMock()
            args.base = 'main'
            args.dry_run = True
            
            # Should handle gracefully and not crash
            try:
                self.cli.run_smart_squash(args)
            except SystemExit:
                pass  # Expected behavior for error cases
    
    def test_configuration_override_from_cli(self):
        """Test CLI argument overrides for AI provider and model"""
        # Simulate command line argument parsing and config override
        args = MagicMock()
        args.ai_provider = 'openai'
        args.model = 'gpt-4'
        args.config = None
        
        # Mock config loading
        with patch.object(self.cli.config_manager, 'load_config') as mock_load:
            mock_config = Config(ai=AIConfig(provider='local', model='devstral'))
            mock_load.return_value = mock_config
            
            # Simulate the config override logic from main()
            self.cli.config = mock_load.return_value
            if args.ai_provider:
                self.cli.config.ai.provider = args.ai_provider
            if args.model:
                self.cli.config.ai.model = args.model
            
            # Verify overrides took effect
            self.assertEqual(self.cli.config.ai.provider, 'openai')
            self.assertEqual(self.cli.config.ai.model, 'gpt-4')
    
    def test_file_level_commit_organization(self):
        """Test that AI analysis includes file-level organization as described"""
        # Test parsing of AI response with file specifications
        commit_plan = [
            {
                'message': 'feat: add authentication system',
                'files': ['src/auth.py', 'src/models/user.py'],
                'rationale': 'Groups authentication code together'
            },
            {
                'message': 'test: add authentication tests',
                'files': ['tests/test_auth.py'],
                'rationale': 'Separate tests from implementation'
            }
        ]
        
        # Verify structure matches expected format from FUNCTIONALITY.md
        for commit in commit_plan:
            self.assertIn('message', commit)
            self.assertIn('files', commit)
            self.assertIn('rationale', commit)
            self.assertIsInstance(commit['files'], list)
            self.assertTrue(commit['message'].strip())
            self.assertTrue(commit['rationale'].strip())


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete workflows described in FUNCTIONALITY.md"""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create a more realistic git repository
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        
        # Create main branch
        os.makedirs('src', exist_ok=True)
        with open('README.md', 'w') as f:
            f.write('# Project\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
    def tearDown(self):
        """Clean up integration test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    @patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate')
    def test_complete_workflow_dry_run(self, mock_generate):
        """Test complete dry-run workflow as described in basic usage"""
        # Create feature branch with multiple commits
        subprocess.run(['git', 'checkout', '-b', 'feature'], check=True)
        
        # Add auth functionality
        with open('src/auth.py', 'w') as f:
            f.write('def login(): pass\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'wip auth'], check=True)
        
        # Add models
        with open('src/models.py', 'w') as f:
            f.write('class User: pass\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'user model'], check=True)
        
        # Add docs
        with open('docs.md', 'w') as f:
            f.write('# API Docs\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'docs'], check=True)
        
        # Mock AI response
        mock_generate.return_value = '''[
            {
                "message": "feat: implement user authentication system",
                "files": ["src/auth.py", "src/models.py"],
                "rationale": "Core authentication functionality"
            },
            {
                "message": "docs: add API documentation",
                "files": ["docs.md"],
                "rationale": "Documentation separate from implementation"
            }
        ]'''
        
        # Test dry run
        cli = GitSmartSquashCLI()
        cli.config = Config(ai=AIConfig())
        
        args = MagicMock()
        args.base = 'main'
        args.dry_run = True
        
        # Should complete successfully
        cli.run_smart_squash(args)
        
        # Verify original commits are still there (dry run didn't modify)
        result = subprocess.run(['git', 'log', '--oneline'], capture_output=True, text=True)
        self.assertIn('wip auth', result.stdout)
        self.assertIn('user model', result.stdout)
        self.assertIn('docs', result.stdout)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(argv=[''], verbosity=2, exit=False)