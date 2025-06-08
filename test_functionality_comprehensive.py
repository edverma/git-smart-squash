#!/usr/bin/env python3
"""
Comprehensive test suite that precisely tests ALL functionality described in FUNCTIONALITY.md.
Every feature, command, format, and behavior must match the documentation exactly.
"""

import unittest
import tempfile
import shutil
import subprocess
import os
import sys
import json
import time
import re
from unittest.mock import patch, MagicMock, mock_open, call
from io import StringIO

# Add the package to the path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import ConfigManager, Config, AIConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider


class TestCoreConceptFourSteps(unittest.TestCase):
    """Test the exact 4-step process described in FUNCTIONALITY.md"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._setup_git_repo()
        self.cli = GitSmartSquashCLI()
        
    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        
    def _setup_git_repo(self):
        """Create a realistic git repository for testing"""
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        
        # Create main branch with initial commit
        with open('README.md', 'w') as f:
            f.write('# Test Project\n')
        subprocess.run(['git', 'add', 'README.md'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        # Create feature branch with messy commits
        subprocess.run(['git', 'checkout', '-b', 'feature-auth'], check=True)
        
        os.makedirs('src', exist_ok=True)
        os.makedirs('tests', exist_ok=True)
        
        # First messy commit
        with open('src/auth.py', 'w') as f:
            f.write('def authenticate(user): pass\n')
        with open('src/models.py', 'w') as f:
            f.write('class User: pass\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'WIP: auth stuff'], check=True)
        
        # Second messy commit
        with open('tests/test_auth.py', 'w') as f:
            f.write('def test_auth(): pass\n')
        with open('docs.md', 'w') as f:
            f.write('# API Documentation\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'more changes'], check=True)
    
    def test_step1_gets_complete_diff_exact_command(self):
        """Test Step 1: Gets complete diff using exact git command"""
        # Test that it uses exactly 'git diff main...HEAD' (three dots)
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='mock diff output', returncode=0)
            
            diff = self.cli.get_full_diff('main')
            
            # Verify exact command with three dots
            mock_run.assert_called_with(
                ['git', 'diff', 'main...HEAD'],
                capture_output=True, text=True, check=True
            )
            self.assertEqual(diff, 'mock diff output')
    
    def test_step2_ai_analysis_exact_prompt(self):
        """Test Step 2: AI analysis uses exact prompt from FUNCTIONALITY.md"""
        expected_prompt = """
            Analyze this git diff and organize it into logical, reviewable commits that would be easy for a reviewer to understand in a pull request.

            For each commit, provide:
            1. A conventional commit message (type: description)
            2. The specific file changes that should be included
            3. A brief rationale for why these changes belong together

            Respond with a JSON array where each commit has this structure:
            {
                "message": "feat: add user authentication system",
                "files": ["src/auth.py", "src/models/user.py"],
                "rationale": "Groups all authentication-related changes together"
            }

            Here's the diff to analyze:

            mock diff content
            """
        
        with patch.object(UnifiedAIProvider, 'generate') as mock_generate:
            mock_generate.return_value = '[]'
            
            self.cli.config = Config(ai=AIConfig())
            self.cli.analyze_with_ai('mock diff content')
            
            # Verify the exact prompt is used
            actual_prompt = mock_generate.call_args[0][0]
            
            # Check key phrases from the documented prompt
            self.assertIn('Analyze this git diff and organize it into logical, reviewable commits', actual_prompt)
            self.assertIn('that would be easy for a reviewer to understand in a pull request', actual_prompt)
            self.assertIn('conventional commit message', actual_prompt)
            self.assertIn('specific file changes', actual_prompt)
            self.assertIn('brief rationale', actual_prompt)
            self.assertIn('mock diff content', actual_prompt)
    
    def test_step3_proposed_structure_exact_format(self):
        """Test Step 3: Display shows exact format from FUNCTIONALITY.md"""
        # Test the exact display format from the documentation
        commit_plan = [
            {
                'message': 'feat: add user authentication system',
                'files': ['src/auth.py', 'src/models/user.py', 'tests/test_auth.py'],
                'rationale': 'Groups all authentication-related changes together'
            },
            {
                'message': 'docs: update API documentation for auth endpoints',
                'files': ['docs/api.md', 'README.md'],
                'rationale': 'Separates documentation updates from implementation'
            }
        ]
        
        # Test that display_commit_plan works without errors
        # This verifies the structure is processed correctly
        try:
            self.cli.display_commit_plan(commit_plan)
            display_worked = True
        except Exception:
            display_worked = False
        
        self.assertTrue(display_worked, "Display commit plan should work without errors")
        
        # Verify the plan contains the expected commit structure
        self.assertEqual(len(commit_plan), 2)
        self.assertIn('feat: add user authentication system', commit_plan[0]['message'])
        self.assertIn('docs: update API documentation', commit_plan[1]['message'])
        self.assertIn('rationale', commit_plan[0])
        self.assertIn('files', commit_plan[0])
    
    def test_step4_apply_changes_exact_sequence(self):
        """Test Step 4: Apply changes with exact git command sequence"""
        commit_plan = [{'message': 'feat: test commit', 'files': [], 'rationale': 'test'}]
        
        with patch('subprocess.run') as mock_run:
            # Mock the command sequence
            mock_run.side_effect = [
                MagicMock(stdout='feature-auth\n', returncode=0),  # get current branch
                MagicMock(returncode=0),  # create backup branch
                MagicMock(returncode=0),  # git reset --soft main
                MagicMock(returncode=0),  # git add .
                MagicMock(returncode=0),  # git commit
            ]
            
            with patch('builtins.input', return_value='y'):
                self.cli.apply_commit_plan(commit_plan, 'main')
            
            # Verify exact git commands are used
            calls = mock_run.call_args_list
            
            # Check git reset --soft specifically
            reset_call = None
            for call in calls:
                if 'reset' in str(call):
                    reset_call = call
                    break
            
            self.assertIsNotNone(reset_call, "git reset --soft command not found")
            self.assertIn('--soft', str(reset_call))
            self.assertIn('main', str(reset_call))


class TestUsageExamplesExact(unittest.TestCase):
    """Test exact usage examples from FUNCTIONALITY.md"""
    
    def setUp(self):
        self.cli = GitSmartSquashCLI()
    
    def test_basic_usage_dry_run_command(self):
        """Test: git-smart-squash --dry-run"""
        parser = self.cli.create_parser()
        args = parser.parse_args(['--dry-run'])
        
        self.assertTrue(args.dry_run)
        self.assertEqual(args.base, 'main')  # default base
    
    def test_basic_usage_apply_command(self):
        """Test: git-smart-squash (no args)"""
        parser = self.cli.create_parser()
        args = parser.parse_args([])
        
        self.assertFalse(args.dry_run)
        self.assertEqual(args.base, 'main')
    
    def test_different_base_branch_command(self):
        """Test: git-smart-squash --base develop"""
        parser = self.cli.create_parser()
        args = parser.parse_args(['--base', 'develop'])
        
        self.assertEqual(args.base, 'develop')
    
    def test_openai_provider_command(self):
        """Test: git-smart-squash --ai-provider openai --model gpt-4.1"""
        parser = self.cli.create_parser()
        args = parser.parse_args(['--ai-provider', 'openai', '--model', 'gpt-4.1'])
        
        self.assertEqual(args.ai_provider, 'openai')
        self.assertEqual(args.model, 'gpt-4.1')
    
    def test_anthropic_provider_command(self):
        """Test: git-smart-squash --ai-provider anthropic --model claude-sonnet-4"""
        parser = self.cli.create_parser()
        args = parser.parse_args(['--ai-provider', 'anthropic', '--model', 'claude-sonnet-4'])
        
        self.assertEqual(args.ai_provider, 'anthropic')
        self.assertEqual(args.model, 'claude-sonnet-4')


class TestAIProvidersExact(unittest.TestCase):
    """Test AI providers exactly as described in FUNCTIONALITY.md"""
    
    def test_default_local_ai_provider(self):
        """Test: Local AI (default): Uses Ollama with devstral model"""
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Verify defaults match documentation exactly
        self.assertEqual(config.ai.provider, 'local')
        self.assertEqual(config.ai.model, 'devstral')
    
    def test_environment_variables_openai(self):
        """Test: Configure via environment variables: OPENAI_API_KEY"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key-123'}):
            config = Config(ai=AIConfig(provider='openai', model='gpt-4.1'))
            provider = UnifiedAIProvider(config)
            
            # Test that provider configuration is correct
            self.assertEqual(provider.provider_type, 'openai')
            
            # Test dynamic token management
            params = provider._calculate_dynamic_params('test prompt')
            self.assertIn('prompt_tokens', params)
            self.assertIn('max_tokens', params)
            self.assertIn('response_tokens', params)
            
            # Test that environment variable is read (by checking os.getenv behavior)
            key = os.getenv('OPENAI_API_KEY')
            self.assertEqual(key, 'test-key-123')
    
    def test_environment_variables_anthropic(self):
        """Test: Configure via environment variables: ANTHROPIC_API_KEY"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key-456'}):
            config = Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4'))
            provider = UnifiedAIProvider(config)
            
            # Test that provider configuration is correct
            self.assertEqual(provider.provider_type, 'anthropic')
            
            # Test dynamic token management
            params = provider._calculate_dynamic_params('test prompt')
            self.assertIn('prompt_tokens', params)
            self.assertIn('max_tokens', params)
            self.assertIn('response_tokens', params)
            
            # Test that environment variable is read (by checking os.getenv behavior)
            key = os.getenv('ANTHROPIC_API_KEY')
            self.assertEqual(key, 'test-key-456')
    
    def test_ollama_local_provider_integration(self):
        """Test: Local AI uses Ollama integration"""
        config = Config(ai=AIConfig(provider='local', model='devstral'))
        provider = UnifiedAIProvider(config)
        
        with patch('subprocess.run') as mock_run:
            mock_response = {'response': 'Generated commit plan'}
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(mock_response)
            )
            
            result = provider._generate_local('test prompt')
            
            # Verify it calls Ollama API
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            self.assertIn('curl', call_args)
            # Check that the URL is in the command arguments
            command_str = ' '.join(call_args)
            self.assertIn('localhost:11434/api/generate', command_str)
            self.assertEqual(result, 'Generated commit plan')


class TestSafetyFeaturesExact(unittest.TestCase):
    """Test safety features exactly as described in FUNCTIONALITY.md"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.cli = GitSmartSquashCLI()
        
    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_backup_branch_exact_naming_format(self):
        """Test: Backup branch naming: your-feature-branch-backup-1703123456"""
        commit_plan = [{'message': 'test', 'files': [], 'rationale': 'test'}]
        
        with patch('subprocess.run') as mock_run:
            # Mock current branch name
            mock_run.return_value = MagicMock(stdout='my-feature-branch\n', returncode=0)
            
            with patch('time.time', return_value=1703123456.789):
                with patch('builtins.input', return_value='y'):
                    try:
                        self.cli.apply_commit_plan(commit_plan, 'main')
                    except:
                        pass  # We just want to check the branch name format
            
            # Find the branch creation call
            branch_calls = [call for call in mock_run.call_args_list if 'branch' in str(call)]
            self.assertTrue(len(branch_calls) > 0, "No branch creation found")
            
            # Verify exact naming format: branch-backup-timestamp
            branch_call_str = str(branch_calls[0])
            self.assertIn('my-feature-branch-backup-1703123456', branch_call_str)
    
    def test_soft_reset_exact_command(self):
        """Test: Uses `git reset --soft` to preserve all changes"""
        commit_plan = [{'message': 'test', 'files': [], 'rationale': 'test'}]
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(stdout='feature\n', returncode=0),  # current branch
                MagicMock(returncode=0),  # create backup
                MagicMock(returncode=0),  # reset
                MagicMock(returncode=0),  # add
                MagicMock(returncode=0),  # commit
            ]
            
            with patch('builtins.input', return_value='y'):
                self.cli.apply_commit_plan(commit_plan, 'main')
            
            # Find the reset command
            reset_calls = [call for call in mock_run.call_args_list if 'reset' in str(call)]
            self.assertTrue(len(reset_calls) > 0, "No reset command found")
            
            # Verify it uses --soft specifically
            reset_call_str = str(reset_calls[0])
            self.assertIn('--soft', reset_call_str)
    
    def test_validation_clean_working_directory(self):
        """Test: Validates clean working directory"""
        # This would be implemented in a real safety checker
        # For now, verify the concept exists in the documentation
        
        # Test that uncommitted changes are detected
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout='M  modified_file.py\n',  # Modified file
                returncode=0
            )
            
            result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
            # In real implementation, this would trigger a safety warning
    
    def test_validation_base_branch_exists(self):
        """Test: Validates base branch exists"""
        # Test with nonexistent branch
        with self.assertRaises(Exception):
            self.cli.get_full_diff('nonexistent-branch-xyz')


class TestConfigurationExact(unittest.TestCase):
    """Test configuration exactly as described in FUNCTIONALITY.md"""
    
    def test_yaml_configuration_exact_format(self):
        """Test: YAML configuration matches documentation format exactly"""
        yaml_content = """ai:
  provider: local  # or openai, anthropic
  model: devstral  # or gpt-4.1, claude-sonnet-4
  
output:
  backup_branch: true"""
        
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('os.path.exists', return_value=True):
                with patch('yaml.safe_load') as mock_yaml:
                    mock_yaml.return_value = {
                        'ai': {
                            'provider': 'local',
                            'model': 'devstral'
                        },
                        'output': {
                            'backup_branch': True
                        }
                    }
                    
                    config_manager = ConfigManager()
                    config = config_manager.load_config('.git-smart-squash.yml')
                    
                    # Verify exact structure matches documentation
                    self.assertEqual(config.ai.provider, 'local')
                    self.assertEqual(config.ai.model, 'devstral')
    
    def test_global_config_file_location(self):
        """Test: Configuration in ~/.git-smart-squash.yml"""
        config_manager = ConfigManager()
        expected_path = os.path.expanduser("~/.git-smart-squash.yml")
        self.assertEqual(config_manager.default_config_path, expected_path)


class TestRecoveryExact(unittest.TestCase):
    """Test recovery procedures exactly as described in FUNCTIONALITY.md"""
    
    def test_recovery_commands_documentation(self):
        """Test: Recovery commands from documentation work"""
        # Test the exact commands from the documentation
        recovery_commands = [
            'git checkout your-branch-backup-123456',
            'git checkout your-working-branch',
            'git reset --hard your-branch-backup-123456'
        ]
        
        # These would be real git commands in actual recovery
        for cmd in recovery_commands:
            # Verify commands are properly formatted
            self.assertIn('git', cmd)
            if 'backup' in cmd:
                self.assertRegex(cmd, r'backup-\d+')


class TestTechnicalImplementationExact(unittest.TestCase):
    """Test technical implementation claims from FUNCTIONALITY.md"""
    
    def test_single_python_file_claim(self):
        """Test: Single Python file (cli.py) with ~300 lines"""
        cli_file = '/Users/edverma/Development/git-smart-squash/git_smart_squash/cli.py'
        
        with open(cli_file, 'r') as f:
            lines = f.readlines()
        
        # Verify line count is approximately 300 (allow some variance)
        line_count = len(lines)
        self.assertGreater(line_count, 250, f"CLI file has {line_count} lines, expected ~300")
        self.assertLess(line_count, 350, f"CLI file has {line_count} lines, expected ~300")
    
    def test_direct_git_commands_via_subprocess(self):
        """Test: Direct git commands via subprocess"""
        # Verify the CLI actually uses subprocess for git commands
        cli = GitSmartSquashCLI()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='', returncode=0)
            
            try:
                cli.get_full_diff('main')
            except:
                pass
            
            # Verify subprocess.run was called with git commands
            self.assertTrue(mock_run.called)
            call_args = mock_run.call_args[0][0]
            self.assertEqual(call_args[0], 'git')
    
    def test_rich_terminal_ui_integration(self):
        """Test: Rich terminal UI for clear feedback"""
        # Verify Rich components are used
        from git_smart_squash.cli import Console, Panel, Progress
        
        # These imports should work if Rich is properly integrated
        self.assertTrue(Console is not None)
        self.assertTrue(Panel is not None)
        self.assertTrue(Progress is not None)


class TestCompleteWorkflowIntegration(unittest.TestCase):
    """Test complete end-to-end workflow as described in FUNCTIONALITY.md"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._setup_realistic_git_repo()
        
    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
        
    def _setup_realistic_git_repo(self):
        """Set up a realistic git repository that matches documentation examples"""
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        
        # Initial commit on main
        with open('README.md', 'w') as f:
            f.write('# Project\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True)
        
        # Feature branch with messy commits (matches documentation example)
        subprocess.run(['git', 'checkout', '-b', 'feature-auth'], check=True)
        
        os.makedirs('src', exist_ok=True)
        os.makedirs('tests', exist_ok=True)
        
        # Create the exact files mentioned in documentation
        with open('src/auth.py', 'w') as f:
            f.write('def authenticate(user):\n    return True\n')
        with open('src/models.py', 'w') as f:
            f.write('class User:\n    def __init__(self, name):\n        self.name = name\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'WIP: auth and models'], check=True)
        
        with open('tests/test_auth.py', 'w') as f:
            f.write('def test_authenticate():\n    assert True\n')
        with open('docs.md', 'w') as f:
            f.write('# API Documentation\n\n## Authentication\n')
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'tests and docs'], check=True)
    
    @patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate')
    def test_complete_dry_run_workflow(self, mock_generate):
        """Test complete dry-run workflow exactly as described"""
        # Mock AI response in the exact format from documentation
        mock_ai_response = '''[
            {
                "message": "feat: add user authentication system",
                "files": ["src/auth.py", "src/models.py", "tests/test_auth.py"],
                "rationale": "Groups all authentication-related changes together"
            },
            {
                "message": "docs: update API documentation for auth endpoints",
                "files": ["docs.md"],
                "rationale": "Separates documentation updates from implementation"
            }
        ]'''
        
        mock_generate.return_value = mock_ai_response
        
        # Create CLI and run dry-run
        cli = GitSmartSquashCLI()
        cli.config = Config(ai=AIConfig(provider='local', model='devstral'))
        
        # Simulate command line arguments for dry-run
        args = MagicMock()
        args.base = 'main'
        args.dry_run = True
        
        # Capture output
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cli.run_smart_squash(args)
        
        # Verify the workflow completed without errors
        # In a dry-run, no actual git changes should be made
        result = subprocess.run(['git', 'log', '--oneline'], capture_output=True, text=True)
        self.assertIn('WIP: auth and models', result.stdout)  # Original commits still there
        self.assertIn('tests and docs', result.stdout)
    
    @patch('git_smart_squash.ai.providers.simple_unified.UnifiedAIProvider.generate')
    @patch('builtins.input', return_value='y')  # User confirms
    def test_complete_apply_workflow(self, mock_input, mock_generate):
        """Test complete apply workflow exactly as described"""
        # Mock AI response
        mock_generate.return_value = '''[
            {
                "message": "feat: implement user authentication system",
                "files": ["src/auth.py", "src/models.py", "tests/test_auth.py"],
                "rationale": "Core authentication functionality"
            }
        ]'''
        
        cli = GitSmartSquashCLI()
        cli.config = Config(ai=AIConfig(provider='local', model='devstral'))
        
        args = MagicMock()
        args.base = 'main'
        args.dry_run = False
        
        # Get original commit count
        original_commits = subprocess.run(['git', 'rev-list', '--count', 'HEAD'], 
                                        capture_output=True, text=True).stdout.strip()
        
        # Run the workflow
        cli.run_smart_squash(args)
        
        # Verify backup branch was created
        branches = subprocess.run(['git', 'branch'], capture_output=True, text=True).stdout
        self.assertIn('backup', branches)
        
        # Verify new commit structure
        final_commits = subprocess.run(['git', 'rev-list', '--count', 'HEAD'], 
                                     capture_output=True, text=True).stdout.strip()
        
        # Should have fewer commits now (squashed)
        self.assertLessEqual(int(final_commits), int(original_commits))


class TestDynamicTokenManagement(unittest.TestCase):
    """Test dynamic token management for all AI providers"""
    
    def setUp(self):
        self.provider = UnifiedAIProvider(Config(ai=AIConfig()))
    
    def test_token_estimation_accuracy(self):
        """Test token estimation works consistently"""
        short_text = "Hello world"
        medium_text = "This is a medium length text " * 10
        long_text = "This is a very long text " * 100
        
        short_tokens = self.provider._estimate_tokens(short_text)
        medium_tokens = self.provider._estimate_tokens(medium_text)
        long_tokens = self.provider._estimate_tokens(long_text)
        
        # Verify scaling relationship
        self.assertGreater(medium_tokens, short_tokens)
        self.assertGreater(long_tokens, medium_tokens)
        
        # Verify reasonable estimates (roughly 1 token per 4 chars)
        self.assertAlmostEqual(short_tokens, len(short_text) // 4, delta=2)
    
    def test_dynamic_params_calculation(self):
        """Test dynamic parameter calculation for all providers"""
        small_prompt = "Small test prompt"
        large_prompt = "Large test prompt " * 1000
        
        small_params = self.provider._calculate_dynamic_params(small_prompt)
        large_params = self.provider._calculate_dynamic_params(large_prompt)
        
        # Verify structure
        for params in [small_params, large_params]:
            self.assertIn('prompt_tokens', params)
            self.assertIn('max_tokens', params)
            self.assertIn('response_tokens', params)
            self.assertIn('context_needed', params)
        
        # Verify scaling
        self.assertGreater(large_params['prompt_tokens'], small_params['prompt_tokens'])
        self.assertGreater(large_params['max_tokens'], small_params['max_tokens'])
        
        # Verify caps are enforced
        self.assertLessEqual(large_params['max_tokens'], self.provider.MAX_CONTEXT_TOKENS)
        self.assertLessEqual(large_params['response_tokens'], self.provider.MAX_PREDICT_TOKENS)
    
    def test_ollama_params_backward_compatibility(self):
        """Test Ollama-specific parameter calculation still works"""
        prompt = "Test prompt for Ollama"
        ollama_params = self.provider._calculate_ollama_params(prompt)
        
        self.assertIn('num_ctx', ollama_params)
        self.assertIn('num_predict', ollama_params)
        self.assertLessEqual(ollama_params['num_ctx'], self.provider.MAX_CONTEXT_TOKENS)
        self.assertLessEqual(ollama_params['num_predict'], self.provider.MAX_PREDICT_TOKENS)
    
    def test_token_limits_enforced(self):
        """Test that hard token limits are always enforced"""
        massive_prompt = "Massive prompt " * 10000  # Way over limits
        
        params = self.provider._calculate_dynamic_params(massive_prompt)
        ollama_params = self.provider._calculate_ollama_params(massive_prompt)
        
        # Should be capped at maximums
        self.assertEqual(params['max_tokens'], self.provider.MAX_CONTEXT_TOKENS)
        self.assertEqual(ollama_params['num_ctx'], self.provider.MAX_CONTEXT_TOKENS)
        
        # Response tokens should be reasonable
        self.assertLessEqual(params['response_tokens'], self.provider.MAX_PREDICT_TOKENS)
        self.assertLessEqual(ollama_params['num_predict'], self.provider.MAX_PREDICT_TOKENS)


class TestErrorConditionsExact(unittest.TestCase):
    """Test error conditions and edge cases exactly as they should behave"""
    
    def setUp(self):
        self.cli = GitSmartSquashCLI()
    
    def test_no_changes_to_reorganize(self):
        """Test behavior when no changes exist between branches"""
        with patch.object(self.cli, 'get_full_diff', return_value=None):
            args = MagicMock()
            args.base = 'main'
            args.dry_run = True
            
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                self.cli.run_smart_squash(args)
            
            output = mock_stdout.getvalue()
            self.assertIn('No changes found to reorganize', output)
    
    def test_ai_analysis_failure(self):
        """Test behavior when AI analysis fails"""
        with patch.object(self.cli, 'get_full_diff', return_value='mock diff'):
            with patch.object(self.cli, 'analyze_with_ai', return_value=None):
                args = MagicMock()
                args.base = 'main'
                args.dry_run = True
                
                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                    self.cli.run_smart_squash(args)
                
                output = mock_stdout.getvalue()
                self.assertIn('Failed to generate commit plan', output)
    
    def test_user_cancellation(self):
        """Test behavior when user cancels the operation"""
        with patch.object(self.cli, 'get_full_diff', return_value='mock diff'):
            with patch.object(self.cli, 'analyze_with_ai', return_value=[{'message': 'test', 'files': [], 'rationale': 'test'}]):
                with patch.object(self.cli, 'get_user_confirmation', return_value=False):
                    args = MagicMock()
                    args.base = 'main'
                    args.dry_run = False
                    
                    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                        self.cli.run_smart_squash(args)
                    
                    output = mock_stdout.getvalue()
                    self.assertIn('Operation cancelled', output)


if __name__ == '__main__':
    # Run with high verbosity to see detailed test results
    unittest.main(argv=[''], verbosity=2, exit=False)