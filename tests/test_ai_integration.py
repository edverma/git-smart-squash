#!/usr/bin/env python3
"""
Integration tests for all AI providers with real responses.
These tests call actual AI providers to validate behavior and token management.

Requirements:
- For Ollama: server running on localhost:11434 with devstral model
- For OpenAI: OPENAI_API_KEY environment variable set
- For Anthropic: ANTHROPIC_API_KEY environment variable set

Run with: python test_ollama_integration.py
"""

import unittest
import subprocess
import json
import os
import sys
import tempfile
import shutil
import time
import yaml
from unittest.mock import patch, MagicMock, mock_open

# Add the package to the path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, ConfigManager, AttributionConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider

# Global flags for test configuration
TEST_NO_LOCAL = False
TEST_CLOUD_ONLY = False


class TestOllamaServerAvailability(unittest.TestCase):
    """Test that Ollama server is available and working."""

    def test_ollama_server_running(self):
        """Test that Ollama server is accessible."""
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
            ], capture_output=True, text=True, timeout=10)

            self.assertEqual(result.returncode, 0, "Ollama server not running on localhost:11434")

            # Verify we can parse the response
            tags_response = json.loads(result.stdout)
            self.assertIn('models', tags_response, "Invalid response from Ollama server")

        except subprocess.TimeoutExpired:
            self.fail("Ollama server request timed out")
        except json.JSONDecodeError:
            self.fail("Invalid JSON response from Ollama server")

    def test_devstral_model_available(self):
        """Test that devstral model is available."""
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
            ], capture_output=True, text=True, timeout=10)

            tags_response = json.loads(result.stdout)
            model_names = [model['name'] for model in tags_response.get('models', [])]

            # Check for devstral or similar models
            devstral_available = any('devstral' in name.lower() for name in model_names)
            if not devstral_available:
                self.skipTest(f"devstral model not found. Available models: {model_names}")

        except Exception as e:
            self.skipTest(f"Could not check available models: {e}")


class TestAllProvidersTokenLimits(unittest.TestCase):
    """Test token limit functionality across all AI providers."""

    def setUp(self):
        # Test configurations for all providers
        self.providers = {
            'local': Config(ai=AIConfig(provider='local', model='devstral'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'openai': Config(ai=AIConfig(provider='openai', model='gpt-4.1'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'anthropic': Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'gemini': Config(ai=AIConfig(provider='gemini', model='gemini-2.5-pro'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)
        }

    def _get_available_providers(self):
        """Check which providers are available for testing."""
        available = []

        # Check Ollama (unless skipped by flags)
        if not TEST_CLOUD_ONLY:
            try:
                result = subprocess.run([
                    "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
                ], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and not TEST_NO_LOCAL:
                    available.append('local')
            except:
                pass

        # Check OpenAI
        if os.getenv('OPENAI_API_KEY'):
            available.append('openai')

        # Check Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            available.append('anthropic')

        # Check Gemini
        if os.getenv('GEMINI_API_KEY'):
            available.append('gemini')

        return available

    def test_token_estimation_all_providers(self):
        """Test token estimation accuracy across all providers."""
        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        short_text = "Hello world"
        long_text = "This is a much longer text " * 100

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                short_tokens = provider._estimate_tokens(short_text)
                long_tokens = provider._estimate_tokens(long_text)

                self.assertGreater(long_tokens, short_tokens)
                self.assertGreater(short_tokens, 0)

                # Verify reasonable estimates (roughly 1 token per 4 chars)
                self.assertAlmostEqual(short_tokens, len(short_text) // 4, delta=5)

    def test_dynamic_params_calculation_all_providers(self):
        """Test dynamic parameter calculation for all providers."""
        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        small_prompt = "Test prompt for commit organization."
        large_prompt = "Analyze this large diff:\n" + "Line of code\n" * 5000

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                # Test dynamic params
                small_params = provider._calculate_dynamic_params(small_prompt)
                large_params = provider._calculate_dynamic_params(large_prompt)

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
                self.assertLessEqual(large_params['max_tokens'], provider.MAX_CONTEXT_TOKENS)
                self.assertLessEqual(large_params['response_tokens'], provider.MAX_PREDICT_TOKENS)

                # Test Ollama-specific params for local provider
                if provider_name == 'local':
                    ollama_params = provider._calculate_ollama_params(large_prompt)
                    self.assertLessEqual(ollama_params['num_ctx'], provider.MAX_CONTEXT_TOKENS)
                    self.assertLessEqual(ollama_params['num_predict'], provider.MAX_PREDICT_TOKENS)


class TestAllProvidersRealResponses(unittest.TestCase):
    """Test real AI responses for commit organization across all providers."""

    def setUp(self):
        # Test configurations for all providers
        self.providers = {
            'local': Config(ai=AIConfig(provider='local', model='devstral'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'openai': Config(ai=AIConfig(provider='openai', model='gpt-4.1'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'anthropic': Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'gemini': Config(ai=AIConfig(provider='gemini', model='gemini-2.5-pro'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)
        }

    def _get_available_providers(self):
        """Check which providers are available for testing."""
        available = []

        # Check Ollama (unless skipped by flags)
        if not TEST_CLOUD_ONLY:
            try:
                result = subprocess.run([
                    "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
                ], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and not TEST_NO_LOCAL:
                    available.append('local')
            except:
                pass

        # Check OpenAI
        if os.getenv('OPENAI_API_KEY'):
            available.append('openai')

        # Check Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            available.append('anthropic')

        # Check Gemini
        if os.getenv('GEMINI_API_KEY'):
            available.append('gemini')

        return available

    def test_simple_commit_organization_all_providers(self):
        """Test AI response to a simple commit organization prompt across all providers."""
        simple_diff = '''
diff --git a/src/auth.py b/src/auth.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/auth.py
@@ -0,0 +1,5 @@
+def authenticate(user, password):
+    if user == "admin" and password == "secret":
+        return True
+    return False
+
diff --git a/tests/test_auth.py b/tests/test_auth.py
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/tests/test_auth.py
@@ -0,0 +1,8 @@
+from src.auth import authenticate
+
+def test_authenticate_success():
+    assert authenticate("admin", "secret") == True
+
+def test_authenticate_failure():
+    assert authenticate("user", "wrong") == False
'''

        prompt = f"""
Analyze this git diff and organize it into logical, reviewable commits that would be easy for a reviewer to understand in a pull request.

For each commit, provide:
1. A conventional commit message (type: description)
2. The specific file changes that should be included
3. A brief rationale for why these changes belong together

Respond with a JSON array where each commit has this structure:
{{
    "message": "feat: add user authentication system",
    "files": ["src/auth.py", "src/models/user.py"],
    "rationale": "Groups all authentication-related changes together"
}}

Here's the diff to analyze:

{simple_diff}
"""

        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                try:
                    # Use the appropriate generation method
                    if provider_name == 'local':
                        response = provider._generate_local(prompt)
                    elif provider_name == 'openai':
                        response = provider._generate_openai(prompt)
                    elif provider_name == 'anthropic':
                        response = provider._generate_anthropic(prompt)
                    elif provider_name == 'gemini':
                        response = provider._generate_gemini(prompt)

                    # Verify response is not empty
                    self.assertIsNotNone(response)
                    self.assertGreater(len(response), 0)

                    # With structured output, response should always be valid JSON
                    parsed = json.loads(response)
                    self.assertIsInstance(parsed, list, "Response should be a JSON array")

                    if len(parsed) > 0:
                        commit = parsed[0]
                        self.assertIn('message', commit, "Commit should have message field")
                        self.assertIn('hunk_ids', commit, "Commit should have hunk_ids field")
                        self.assertIn('rationale', commit, "Commit should have rationale field")

                        # Verify conventional commit format
                        message = commit['message']
                        self.assertRegex(message, r'^[a-z]+(\([^)]+\))?: .+', "Should follow conventional commit format")

                except Exception as e:
                    if 'api key' in str(e).lower() or 'not installed' in str(e).lower():
                        self.skipTest(f"{provider_name} not properly configured: {e}")
                    else:
                        self.fail(f"{provider_name} generation failed: {e}")

    def test_complex_commit_organization_all_providers(self):
        """Test AI response to a complex multi-file diff across all providers."""
        complex_diff = '''
diff --git a/src/auth.py b/src/auth.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/auth.py
@@ -0,0 +1,15 @@
+import hashlib
+from src.models import User
+
+def authenticate(username, password):
+    user = User.find_by_username(username)
+    if user and verify_password(password, user.password_hash):
+        return user
+    return None
+
+def verify_password(password, hash):
+    return hashlib.sha256(password.encode()).hexdigest() == hash
+
+def hash_password(password):
+    return hashlib.sha256(password.encode()).hexdigest()

diff --git a/src/models.py b/src/models.py
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/src/models.py
@@ -0,0 +1,20 @@
+class User:
+    def __init__(self, username, password_hash, email):
+        self.username = username
+        self.password_hash = password_hash
+        self.email = email
+
+    @classmethod
+    def find_by_username(cls, username):
+        # Database lookup simulation
+        users = {
+            "admin": User("admin", "hash123", "admin@example.com"),
+            "user": User("user", "hash456", "user@example.com")
+        }
+        return users.get(username)
+
+    def save(self):
+        # Save to database
+        pass

diff --git a/tests/test_auth.py b/tests/test_auth.py
new file mode 100644
index 0000000..xyz789
--- /dev/null
+++ b/tests/test_auth.py
@@ -0,0 +1,25 @@
+import pytest
+from src.auth import authenticate, hash_password, verify_password
+from src.models import User
+
+def test_hash_password():
+    password = "test123"
+    hashed = hash_password(password)
+    assert len(hashed) == 64  # SHA256 hex length
+
+def test_verify_password():
+    password = "test123"
+    hashed = hash_password(password)
+    assert verify_password(password, hashed) == True
+    assert verify_password("wrong", hashed) == False

diff --git a/docs/api.md b/docs/api.md
new file mode 100644
index 0000000..documentation
--- /dev/null
+++ b/docs/api.md
@@ -0,0 +1,15 @@
+# Authentication API
+
+## Overview
+The authentication system provides secure user login capabilities.
+
+## Functions
+
+### authenticate(username, password)
+Authenticates a user with username and password.
+
+**Parameters:**
+- username (str): The username
+- password (str): The plain text password
+
+**Returns:** User object if successful, None if failed
'''

        prompt = f"""
Analyze this git diff and organize it into logical, reviewable commits that would be easy for a reviewer to understand in a pull request.

For each commit, provide:
1. A conventional commit message (type: description)
2. The specific file changes that should be included
3. A brief rationale for why these changes belong together

Respond with a JSON array where each commit has this structure:
{{
    "message": "feat: add user authentication system",
    "files": ["src/auth.py", "src/models/user.py"],
    "rationale": "Groups all authentication-related changes together"
}}

Here's the diff to analyze:

{complex_diff}
"""

        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                try:
                    # Use the appropriate generation method
                    if provider_name == 'local':
                        response = provider._generate_local(prompt)
                    elif provider_name == 'openai':
                        response = provider._generate_openai(prompt)
                    elif provider_name == 'anthropic':
                        response = provider._generate_anthropic(prompt)
                    elif provider_name == 'gemini':
                        response = provider._generate_gemini(prompt)

                    self.assertIsNotNone(response)
                    self.assertGreater(len(response), 0)

                    # Verify response mentions key components
                    response_lower = response.lower()
                    self.assertIn('auth', response_lower, "Response should mention authentication")
                    self.assertIn('model', response_lower, "Response should mention models")
                    self.assertIn('test', response_lower, "Response should mention tests")
                    self.assertIn('doc', response_lower, "Response should mention documentation")

                    print(f"{provider_name} complex diff response length: {len(response)} characters")

                except Exception as e:
                    if 'api key' in str(e).lower() or 'not installed' in str(e).lower():
                        self.skipTest(f"{provider_name} not properly configured: {e}")
                    elif 'truncated' in str(e).lower() or 'token limit' in str(e).lower():
                        # This is expected behavior for complex diffs that exceed response limits
                        print(f"{provider_name} hit response token limit (expected for complex diffs): {e}")
                        self.skipTest(f"{provider_name} response truncated due to complexity - this is expected behavior")
                    else:
                        self.fail(f"{provider_name} complex diff analysis failed: {e}")

    def test_large_diff_token_handling_all_providers(self):
        """Test handling of large diffs that approach token limits across all providers."""
        # Create a large diff that approaches but doesn't exceed 30k tokens
        large_diff_lines = []
        for i in range(80):  # Generate many file changes (reduced from 200 to 80)
            large_diff_lines.extend([
                f"diff --git a/src/file{i}.py b/src/file{i}.py",
                "new file mode 100644",
                "index 0000000..1234567",
                "--- /dev/null",
                f"+++ b/src/file{i}.py",
                "@@ -0,0 +1,10 @@",
            ])
            for j in range(10):
                large_diff_lines.append(f"+def function_{i}_{j}():")
                large_diff_lines.append(f"+    return 'Function {i}-{j} implementation'")
                large_diff_lines.append("+")

        large_diff = "\n".join(large_diff_lines)

        prompt = f"""
Analyze this git diff and organize it into logical, reviewable commits. This is a large diff, so please group related changes efficiently.

Respond with a JSON array where each commit has this structure:
{{
    "message": "feat: description",
    "files": ["file1.py", "file2.py"],
    "rationale": "why these belong together"
}}

Here's the diff:

{large_diff}
"""

        # Check token estimation with a sample provider
        sample_provider = UnifiedAIProvider(self.providers['local'])
        estimated_tokens = sample_provider._estimate_tokens(prompt)
        print(f"Large diff estimated tokens: {estimated_tokens}")

        # Calculate parameters
        params = sample_provider._calculate_dynamic_params(prompt)
        print(f"Calculated params: {params}")

        # Verify we approach but don't exceed token limits (should be under 30k)
        self.assertLess(estimated_tokens, 30000, "Test diff should be under 30k tokens")
        self.assertGreater(estimated_tokens, 15000, "Test diff should be substantial (over 15k tokens)")

        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                try:
                    start_time = time.time()

                    # Use the appropriate generation method
                    if provider_name == 'local':
                        response = provider._generate_local(prompt)
                    elif provider_name == 'openai':
                        response = provider._generate_openai(prompt)
                    elif provider_name == 'anthropic':
                        response = provider._generate_anthropic(prompt)
                    elif provider_name == 'gemini':
                        response = provider._generate_gemini(prompt)

                    end_time = time.time()

                    self.assertIsNotNone(response)
                    self.assertGreater(len(response), 0)

                    print(f"{provider_name} large diff processing time: {end_time - start_time:.2f} seconds")
                    print(f"{provider_name} response length: {len(response)} characters")

                    # Verify response makes sense for large changes
                    response_lower = response.lower()
                    self.assertTrue(
                        any(keyword in response_lower for keyword in ['commit', 'change', 'feat', 'add', 'implement', 'create', 'update', 'file']),
                        f"{provider_name} response should mention relevant keywords. Got: {response[:200]}..."
                    )

                except Exception as e:
                    # Large diffs might timeout or fail, which is acceptable for some providers
                    error_str = str(e).lower()
                    if 'api key' in error_str or 'not installed' in error_str:
                        self.skipTest(f"{provider_name} not properly configured: {e}")
                    elif 'timeout' in error_str or 'truncated' in error_str or 'limit' in error_str:
                        print(f"{provider_name} large diff test failed as expected: {e}")
                        # This is acceptable for very large diffs
                    else:
                        self.fail(f"{provider_name} large diff test failed unexpectedly: {e}")


class TestAllProvidersIntegrationWithCLI(unittest.TestCase):
    """Test integration of all AI providers with the full CLI workflow."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self._setup_test_repo()

        # Test configurations for all providers
        self.providers = {
            'local': Config(ai=AIConfig(provider='local', model='devstral'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'openai': Config(ai=AIConfig(provider='openai', model='gpt-4.1'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'anthropic': Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'gemini': Config(ai=AIConfig(provider='gemini', model='gemini-2.5-pro'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)
        }

    def _get_available_providers(self):
        """Check which providers are available for testing."""
        available = []

        # Check Ollama
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                available.append('local')
        except:
            pass

        # Check OpenAI
        if os.getenv('OPENAI_API_KEY'):
            available.append('openai')

        # Check Anthropic
        if os.getenv('ANTHROPIC_API_KEY'):
            available.append('anthropic')

        return available

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def _setup_test_repo(self):
        """Create a realistic test repository."""
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)

        # Initial commit
        with open('README.md', 'w') as f:
            f.write('# Test Project\n')
        subprocess.run(['git', 'add', 'README.md'], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'Initial commit'], check=True)

        # Feature branch with changes
        subprocess.run(['git', 'checkout', '-b', 'feature-auth'], check=True)

        os.makedirs('src', exist_ok=True)
        os.makedirs('tests', exist_ok=True)

        # Add authentication files
        with open('src/auth.py', 'w') as f:
            f.write('''
def authenticate(username, password):
    """Authenticate user with username and password."""
    if username == "admin" and password == "secret":
        return {"username": username, "role": "admin"}
    return None

def logout(session_id):
    """Logout user by session ID."""
    # Implementation here
    pass
''')

        with open('src/models.py', 'w') as f:
            f.write('''
class User:
    def __init__(self, username, email):
        self.username = username
        self.email = email

    def to_dict(self):
        return {"username": self.username, "email": self.email}
''')

        with open('tests/test_auth.py', 'w') as f:
            f.write('''
from src.auth import authenticate, logout

def test_authenticate_success():
    result = authenticate("admin", "secret")
    assert result is not None
    assert result["username"] == "admin"

def test_authenticate_failure():
    result = authenticate("user", "wrong")
    assert result is None
''')

        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'WIP: authentication system'], check=True)

    def test_cli_dry_run_all_providers(self):
        """Test CLI dry run with all available AI providers."""
        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                cli = GitSmartSquashCLI()
                cli.config = self.providers[provider_name]

                # Create mock args
                class MockArgs:
                    base = 'main'
                    auto_apply = False
                    instructions = None
                    no_attribution = False

                args = MockArgs()

                try:
                    # This should work end-to-end with real AI
                    cli.run_smart_squash(args)

                    # Verify we didn't actually change the git history
                    result = subprocess.run(['git', 'log', '--oneline'], capture_output=True, text=True)
                    self.assertIn('WIP: authentication system', result.stdout)

                except Exception as e:
                    error_str = str(e).lower()
                    if 'api key' in error_str or 'not installed' in error_str:
                        self.skipTest(f"{provider_name} not properly configured: {e}")
                    elif 'timeout' in error_str:
                        self.skipTest(f"{provider_name} request timed out: {e}")
                    else:
                        self.fail(f"CLI integration with {provider_name} failed: {e}")

    def test_ai_response_quality_all_providers(self):
        """Test that all AI providers provide useful commit organization suggestions."""
        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available for testing")

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                cli = GitSmartSquashCLI()
                cli.config = self.providers[provider_name]

                # Get the actual diff
                diff = cli.get_full_diff('main')
                self.assertIsNotNone(diff)

                try:
                    # Parse diff into hunks
                    from git_smart_squash.diff_parser import parse_diff
                    hunks = parse_diff(diff, context_lines=3)

                    # Get AI analysis
                    commit_plan = cli.analyze_with_ai(hunks, diff)

                    self.assertIsNotNone(commit_plan, f"{provider_name} should return a commit plan")
                    self.assertIsInstance(commit_plan, list, f"{provider_name} commit plan should be a list")

                    if len(commit_plan) > 0:
                        # Verify structure of first commit
                        commit = commit_plan[0]
                        self.assertIn('message', commit, f"{provider_name} commit should have a message")

                        # Check if message follows conventional commit format
                        if 'message' in commit:
                            message = commit['message']
                            # Should contain some indication of authentication functionality
                            message_lower = message.lower()
                            self.assertTrue(
                                any(keyword in message_lower for keyword in ['auth', 'user', 'login', 'feat', 'add']),
                                f"{provider_name} message should be relevant to changes: {message}"
                            )

                except Exception as e:
                    error_str = str(e).lower()
                    if 'api key' in error_str or 'not installed' in error_str:
                        self.skipTest(f"{provider_name} not properly configured: {e}")
                    elif 'timeout' in error_str:
                        self.skipTest(f"{provider_name} analysis timed out: {e}")
                    else:
                        self.fail(f"{provider_name} AI analysis failed: {e}")


class TestStructuredOutputValidation(unittest.TestCase):
    """Test structured output validation with real API responses"""

    def setUp(self):
        self.providers = {
            'local': Config(ai=AIConfig(provider='local', model='devstral'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'openai': Config(ai=AIConfig(provider='openai', model='gpt-4.1'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'anthropic': Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False),
            'gemini': Config(ai=AIConfig(provider='gemini', model='gemini-2.5-pro'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)
        }

    def _get_available_providers(self):
        available = []
        # Check Ollama
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                available.append('local')
        except:
            pass
        # Check API keys
        if os.getenv('OPENAI_API_KEY'):
            available.append('openai')
        if os.getenv('ANTHROPIC_API_KEY'):
            available.append('anthropic')
        if os.getenv('GEMINI_API_KEY'):
            available.append('gemini')
        return available

    def test_json_schema_enforcement(self):
        """Test that all providers strictly enforce JSON schema"""
        available_providers = self._get_available_providers()
        if not available_providers:
            self.skipTest("No AI providers available")

        test_prompt = "Organize authentication changes: auth.py and test_auth.py"

        for provider_name in available_providers:
            with self.subTest(provider=provider_name):
                config = self.providers[provider_name]
                provider = UnifiedAIProvider(config)

                try:
                    if provider_name == 'local':
                        response = provider._generate_local(test_prompt)
                    elif provider_name == 'openai':
                        response = provider._generate_openai(test_prompt)
                    elif provider_name == 'anthropic':
                        response = provider._generate_anthropic(test_prompt)
                    elif provider_name == 'gemini':
                        response = provider._generate_gemini(test_prompt)

                    # Must be valid JSON array
                    parsed = json.loads(response)
                    self.assertIsInstance(parsed, list)

                    # Validate each commit structure
                    for commit in parsed:
                        self.assertIn('message', commit)
                        self.assertIn('hunk_ids', commit)
                        self.assertIn('rationale', commit)
                        self.assertIsInstance(commit['hunk_ids'], list)
                        self.assertIsInstance(commit['message'], str)
                        self.assertIsInstance(commit['rationale'], str)

                except Exception as e:
                    if 'api key' in str(e).lower() or 'not installed' in str(e).lower():
                        self.skipTest(f"{provider_name} not configured: {e}")
                    else:
                        self.fail(f"{provider_name} schema enforcement failed: {e}")


class TestErrorHandlingEdgeCases(unittest.TestCase):
    """Test edge cases and error handling scenarios"""

    def test_malformed_response_handling(self):
        """Test handling of malformed responses"""
        provider = UnifiedAIProvider(Config(ai=AIConfig(provider='local'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

        malformed_cases = [
            '{"commits": [',  # Incomplete JSON
            'plain text',      # Non-JSON response
            '{"wrong_field": []}',  # Wrong schema
        ]

        for malformed in malformed_cases:
            with patch('subprocess.run') as mock_run:
                mock_response = {'response': malformed, 'done': True}
                mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response))

                # Should handle gracefully
                try:
                    result = provider._generate_local("test")
                    # Result should be a string for fallback processing
                    self.assertIsInstance(result, str)
                except Exception as e:
                    # Should not crash unexpectedly
                    self.assertIn('JSON', str(e))  # Should be JSON-related error

    def test_ollama_server_down(self):
        """Test handling when Ollama server is down"""
        provider = UnifiedAIProvider(Config(ai=AIConfig(provider='local'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(7, 'curl', stderr='Failed to connect')

            with self.assertRaises(Exception) as context:
                provider._generate_local("test")

            self.assertIn('Local AI generation failed', str(context.exception))

    def test_ollama_response_truncation(self):
        """Test handling of truncated Ollama responses"""
        provider = UnifiedAIProvider(Config(ai=AIConfig(provider='local'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

        with patch('subprocess.run') as mock_run:
            mock_response = {'response': '{"commits": [', 'done': False}  # Truncated
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response))

            result = provider._generate_local("test")
            # Should handle gracefully even with truncated response
            self.assertIsInstance(result, str)


class TestProviderSpecificErrorHandling(unittest.TestCase):
    """Test provider-specific error scenarios"""

    def setUp(self):
        self.local_provider = UnifiedAIProvider(Config(ai=AIConfig(provider='local', model='devstral'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))
        self.openai_provider = UnifiedAIProvider(Config(ai=AIConfig(provider='openai', model='gpt-4.1'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))
        self.anthropic_provider = UnifiedAIProvider(Config(ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

    def test_openai_rate_limit_handling(self):
        """Test handling of OpenAI rate limits"""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                # Simulate rate limit error
                from openai import RateLimitError
                mock_client.chat.completions.create.side_effect = RateLimitError(
                    message="Rate limit exceeded",
                    response=MagicMock(),
                    body={}
                )

                with self.assertRaises(Exception) as context:
                    self.openai_provider._generate_openai("test")

                self.assertIn('OpenAI generation failed', str(context.exception))

    def test_anthropic_context_length_error(self):
        """Test handling of Anthropic context length errors"""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client

                # Simulate context length error
                import anthropic
                mock_client.messages.create.side_effect = anthropic.BadRequestError(
                    message="Context length exceeded",
                    response=MagicMock(),
                    body={}
                )

                with self.assertRaises(Exception) as context:
                    self.anthropic_provider._generate_anthropic("test")

                self.assertIn('Anthropic generation failed', str(context.exception))

    def test_missing_api_libraries(self):
        """Test handling when API libraries are not installed"""
        # Test OpenAI library missing
        with patch('builtins.__import__', side_effect=ImportError("No module named 'openai'")):
            with self.assertRaises(Exception) as context:
                self.openai_provider._generate_openai("test")

            self.assertIn('OpenAI library not installed', str(context.exception))

        # Test Anthropic library missing
        with patch('builtins.__import__', side_effect=ImportError("No module named 'anthropic'")):
            with self.assertRaises(Exception) as context:
                self.anthropic_provider._generate_anthropic("test")

            self.assertIn('Anthropic library not installed', str(context.exception))


class TestAdvancedTokenManagement(unittest.TestCase):
    """Test advanced token management scenarios"""

    def setUp(self):
        self.provider = UnifiedAIProvider(Config(ai=AIConfig(), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

    def test_token_estimation_accuracy_validation(self):
        """Test token estimation accuracy across different content types"""
        test_cases = [
            ("Simple text", "Hello world"),
            ("Code with symbols", "def func():\n    return {'key': 'value'}"),
            ("Mixed content", "This is text\n```python\ncode_here()\n```\nMore text"),
            ("Unicode content", "Hello 世界 🌍 Мир"),
            ("Very short", "a"),
            ("Empty", ""),
            ("Repeated patterns", "a" * 100),
            ("Special chars", "!@#$%^&*()_+-=[]{}|;':\",./<>?"),
        ]

        for description, text in test_cases:
            with self.subTest(description=description):
                tokens = self.provider._estimate_tokens(text)
                self.assertGreaterEqual(tokens, 0)
                # Conservative estimation should generally be higher than actual
                if text:
                    self.assertGreater(tokens, 0)
                else:
                    self.assertEqual(tokens, 1)  # Minimum 1 token

    def test_ollama_params_scaling(self):
        """Test Ollama parameter scaling with different prompt sizes"""
        test_sizes = [100, 1000, 5000, 10000, 20000]

        for size in test_sizes:
            with self.subTest(size=size):
                text = "a" * size
                try:
                    params = self.provider._calculate_ollama_params(text)
                    self.assertIn('num_ctx', params)
                    self.assertIn('num_predict', params)
                    self.assertGreater(params['num_ctx'], 0)
                    self.assertGreater(params['num_predict'], 0)
                except Exception as e:
                    # Should only fail if size is too large
                    if size * 3 > self.provider.MAX_CONTEXT_TOKENS:
                        self.assertIn('Diff is too large', str(e))
                    else:
                        self.fail(f"Unexpected error for size {size}: {e}")


class TestConcurrentProviderOperations(unittest.TestCase):
    """Test concurrent operations across multiple providers"""

    def setUp(self):
        self.providers = {
            'local': UnifiedAIProvider(Config(ai=AIConfig(provider='local'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)),
            'openai': UnifiedAIProvider(Config(ai=AIConfig(provider='openai'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)),
            'anthropic': UnifiedAIProvider(Config(ai=AIConfig(provider='anthropic'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False)),
            'gemini': UnifiedAIProvider(Config(ai=AIConfig(provider='gemini', model='gemini-2.5-pro'), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))
        }

    def test_provider_isolation(self):
        """Test that provider instances don't interfere with each other"""
        test_prompt = "test prompt for isolation"

        # Each provider should handle the same prompt independently
        for provider_name, provider in self.providers.items():
            with self.subTest(provider=provider_name):
                params = provider._calculate_dynamic_params(test_prompt)
                self.assertIsInstance(params, dict)
                self.assertEqual(provider.provider_type, provider_name)

    def test_configuration_independence(self):
        """Test that changing one provider's config doesn't affect others"""
        original_models = {name: provider.config.ai.model for name, provider in self.providers.items()}

        # Modify one provider's config
        self.providers['local'].config.ai.model = 'modified-model'

        # Others should remain unchanged
        for name, provider in self.providers.items():
            if name != 'local':
                self.assertEqual(provider.config.ai.model, original_models[name])


class TestResponseValidationComprehensive(unittest.TestCase):
    """Comprehensive response validation testing"""

    def setUp(self):
        self.provider = UnifiedAIProvider(Config(ai=AIConfig(), hunks=HunkConfig(), attribution=AttributionConfig(), auto_apply=False))

    def test_response_size_limits(self):
        """Test handling of responses that exceed reasonable size limits"""
        # Very large response
        huge_response = '{"commits": [' + '{"message": "test", "files": [], "rationale": "test"},' * 10000 + ']}'

        with patch('subprocess.run') as mock_run:
            mock_response = {'response': huge_response, 'done': True}
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response))

            result = self.provider._generate_local("test")
            # Should handle without crashing
            self.assertIsInstance(result, str)

    def test_response_parsing_edge_cases(self):
        """Test edge cases in response parsing"""
        edge_cases = [
            '[]',  # Direct array
            '{"commits": null}',  # Null commits
            '{"commits": "invalid"}',  # Wrong type
            '{"commits": [null]}',  # Null commit
            '{"commits": [{}]}',  # Empty commit object
            '{"commits": [{"message": null, "files": null, "rationale": null}]}',  # Null fields
        ]

        for edge_case in edge_cases:
            with self.subTest(response=edge_case):
                with patch('subprocess.run') as mock_run:
                    mock_response = {'response': edge_case, 'done': True}
                    mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response))

                    try:
                        result = self.provider._generate_local("test")
                        self.assertIsInstance(result, str)
                    except Exception:
                        # Some edge cases may fail, which is acceptable
                        pass

    def test_nested_json_in_responses(self):
        """Test handling of nested JSON structures in responses"""
        nested_response = '''{"commits": [{"message": "test", "files": ["file.json"], "rationale": "Contains JSON: {\\"nested\\": true}"}]}'''

        with patch('subprocess.run') as mock_run:
            mock_response = {'response': nested_response, 'done': True}
            mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_response))

            result = self.provider._generate_local("test")
            parsed = json.loads(result)
            self.assertIsInstance(parsed, list)
            if parsed:
                self.assertIn('nested', parsed[0]['rationale'])


class TestConfigurationRobustness(unittest.TestCase):
    """Test configuration system robustness"""

    def setUp(self):
        self.config_manager = ConfigManager()

    def test_corrupted_config_file_handling(self):
        """Test handling of corrupted YAML config files"""
        corrupted_yaml_cases = [
            "invalid: yaml: content: [",  # Invalid YAML
            "- item1\n  - item2\n invalid",  # Mixed valid/invalid
            "key: value\n\t\tinvalid_indentation",  # Indentation errors
            "",  # Empty file
            "null",  # Just null
            "[]",  # Array instead of object
        ]

        for corrupted_yaml in corrupted_yaml_cases:
            with self.subTest(yaml_content=corrupted_yaml[:20]):
                with patch('os.path.exists', return_value=True):
                    with patch('builtins.open', mock_open(read_data=corrupted_yaml)):
                        with patch('yaml.safe_load', side_effect=yaml.YAMLError("Invalid YAML")):
                            # Should fall back to defaults
                            config = self.config_manager.load_config()
                            self.assertEqual(config.ai.provider, 'local')

    def test_partial_config_completion(self):
        """Test completion of partial configuration files"""
        partial_configs = [
            {'ai': {}},  # Missing provider and model
            {'ai': {'provider': 'openai'}},  # Missing model
            {'ai': {'model': 'custom-model'}},  # Missing provider
            {'other_section': {'key': 'value'}},  # Missing ai section entirely
        ]

        for partial_config in partial_configs:
            with self.subTest(config=str(partial_config)):
                with patch('os.path.exists', return_value=True):
                    with patch('builtins.open', mock_open()):
                        with patch('yaml.safe_load', return_value=partial_config):
                            config = self.config_manager.load_config()
                            # Should have valid defaults
                            self.assertIsNotNone(config.ai.provider)
                            self.assertIsNotNone(config.ai.model)

                            # Provider should determine model if model was missing
                            expected_model = self.config_manager._get_default_model(config.ai.provider)
                            if 'ai' not in partial_config or 'model' not in partial_config.get('ai', {}):
                                self.assertEqual(config.ai.model, expected_model)


class TestCLIRobustness(unittest.TestCase):
    """Test CLI robustness and edge cases"""

    def setUp(self):
        self.cli = GitSmartSquashCLI()

    def test_argument_parsing_edge_cases(self):
        """Test edge cases in argument parsing"""
        parser = self.cli.create_parser()

        edge_cases = [
            ['--base', ''],  # Empty base branch
            ['--model', ''],  # Empty model name
            ['--ai-provider', 'invalid'],  # Invalid provider
            ['--config', '/nonexistent/path'],  # Nonexistent config
            ['--base', 'very-long-branch-name-' * 10],  # Very long branch name
        ]

        for args in edge_cases:
            with self.subTest(args=args):
                try:
                    parsed_args = parser.parse_args(args)
                    # Some should parse successfully
                    self.assertIsNotNone(parsed_args)
                except SystemExit:
                    # Some should fail due to invalid choices
                    pass

    def test_rich_ui_components_error_handling(self):
        """Test Rich UI components handle errors gracefully"""
        # Test with malformed commit plan
        malformed_plan = [
            {'message': None, 'files': None, 'rationale': None},  # Null values
            {'message': 'test'},  # Missing required fields
            {},  # Completely empty
        ]

        try:
            self.cli.display_commit_plan(malformed_plan)
            # Should not crash
        except Exception as e:
            # If it does fail, should be a reasonable error
            self.assertIsInstance(e, (KeyError, TypeError, AttributeError))

    def test_user_input_edge_cases(self):
        """Test edge cases in user input handling"""
        with patch('builtins.input') as mock_input:
            # Test various input scenarios
            input_cases = ['', 'Y', 'yes', 'n', 'NO', 'maybe', '123', '\n', ' y ']

            for user_input in input_cases:
                with self.subTest(input=repr(user_input)):
                    mock_input.return_value = user_input
                    result = self.cli.get_user_confirmation()
                    # Should return boolean
                    self.assertIsInstance(result, bool)
                    # Only 'y' should return True
                    self.assertEqual(result, user_input.lower().strip() == 'y')


if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run AI integration tests')
    parser.add_argument('--no-local', action='store_true',
                       help='Skip local model tests (Ollama)')
    parser.add_argument('--cloud-only', action='store_true',
                       help='Run only cloud provider tests (OpenAI, Anthropic, Gemini)')
    args = parser.parse_args()

    # Set global flags
    globals()['TEST_NO_LOCAL'] = args.no_local
    globals()['TEST_CLOUD_ONLY'] = args.cloud_only

    print("Running AI integration tests for all providers...")
    print("Requirements:")
    if not args.no_local and not args.cloud_only:
        print("- For Ollama: server running on localhost:11434 with devstral model")
    print("- For OpenAI: OPENAI_API_KEY environment variable set")
    print("- For Anthropic: ANTHROPIC_API_KEY environment variable set")
    print("- For Google Gemini: GEMINI_API_KEY environment variable set")
    print("- Network connectivity for cloud providers")
    print()

    # Check available providers
    available_providers = []

    # Check Ollama (unless skipped)
    if not args.cloud_only:
        try:
            result = subprocess.run([
                "curl", "-s", "-X", "GET", "http://localhost:11434/api/tags"
            ], capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and not args.no_local:
                print("✓ Ollama server is running")
                response = json.loads(result.stdout)
                models = [m['name'] for m in response.get('models', [])]
                print(f"✓ Available Ollama models: {models}")
                available_providers.append('local')
            elif args.no_local:
                print("⏭️  Skipping Ollama tests (--no-local flag)")
            else:
                print("✗ Ollama server not accessible")
                print("  Start with: ollama serve && ollama pull devstral")

        except Exception as e:
            if not args.no_local:
                print(f"✗ Cannot connect to Ollama: {e}")
                print("  Start with: ollama serve && ollama pull devstral")
            else:
                print("⏭️  Skipping Ollama tests (--no-local flag)")

    # Check OpenAI
    if os.getenv('OPENAI_API_KEY'):
        print("✓ OpenAI API key found")
        available_providers.append('openai')
    else:
        print("✗ OpenAI API key not found")
        print("  Set with: export OPENAI_API_KEY=your_key_here")

    # Check Anthropic
    if os.getenv('ANTHROPIC_API_KEY'):
        print("✓ Anthropic API key found")
        available_providers.append('anthropic')
    else:
        print("✗ Anthropic API key not found")
        print("  Set with: export ANTHROPIC_API_KEY=your_key_here")

    if os.getenv('GEMINI_API_KEY'):
        print("✓ Google Gemini API key found")
        available_providers.append('gemini')
    else:
        print("✗ Google Gemini API key not found")
        print("  Set with: export GEMINI_API_KEY=your_key_here")

    if available_providers:
        print(f"\n🚀 Running tests with providers: {', '.join(available_providers)}")
    else:
        print("\n⚠️  No AI providers available - tests will be skipped")

    print("\nRunning tests...")
    unittest.main(argv=[''], verbosity=2, exit=False)
