"""Tests for enhanced features implementing TECHNICAL_SPECIFICATION.md."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import shutil
from datetime import datetime

from ..zero_friction import ZeroFrictionEngine
from ..models import Commit, CommitGroup, Config, AIConfig, GroupingConfig
from ..ai.message_generator import MessageGenerator, TemplateMessageGenerator
from ..grouping.grouping_engine import GroupingEngine
from ..utils.performance import PerformanceOptimizer, RepositoryAnalyzer


class TestZeroFrictionEngine(unittest.TestCase):
    """Test the enhanced zero friction engine."""
    
    def setUp(self):
        self.engine = ZeroFrictionEngine()
    
    def test_detect_ai_provider_ollama(self):
        """Test AI provider detection prioritizes Ollama."""
        with patch.object(self.engine, '_check_ollama', return_value=True):
            provider, model, base_url = self.engine.detect_ai_provider()
            self.assertEqual(provider, "local")
            self.assertEqual(model, "devstral")
            self.assertEqual(base_url, "http://localhost:11434")
    
    def test_detect_ai_provider_openai(self):
        """Test AI provider detection falls back to OpenAI."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch.object(self.engine, '_check_ollama', return_value=False):
                provider, model, base_url = self.engine.detect_ai_provider()
                self.assertEqual(provider, "openai")
                self.assertEqual(model, "gpt-4o-mini")
                self.assertIsNone(base_url)
    
    def test_detect_ai_provider_template_fallback(self):
        """Test AI provider detection falls back to templates."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(self.engine, '_check_ollama', return_value=False):
                provider, model, base_url = self.engine.detect_ai_provider()
                self.assertEqual(provider, "template")
                self.assertIsNone(model)
                self.assertIsNone(base_url)
    
    def test_confidence_scoring(self):
        """Test the enhanced confidence scoring system."""
        # Create test groups
        good_groups = [
            self._create_test_group("group1", 3, "feat: add user authentication"),
            self._create_test_group("group2", 2, "fix: resolve login issue")
        ]
        
        bad_groups = [
            self._create_test_group("group1", 1, "wip"),
            self._create_test_group("group2", 1, "temp"),
            self._create_test_group("group3", 1, "fix"),
        ]
        
        # Good groups should have high confidence
        good_score = self.engine.calculate_confidence_score(good_groups, [])
        self.assertGreater(good_score, 0.7)
        
        # Bad groups should have low confidence
        bad_score = self.engine.calculate_confidence_score(bad_groups, ["warning"])
        self.assertLess(bad_score, 0.5)
    
    def test_auto_fix_safety_issues(self):
        """Test automatic safety issue resolution."""
        with patch('subprocess.run') as mock_run:
            with patch.object(self.engine.parser, 'get_current_branch', return_value='main'):
                mock_run.return_value = Mock(returncode=0)
                
                success, actions = self.engine.auto_fix_safety_issues()
                
                self.assertTrue(success)
                self.assertIn("Created working branch", ' '.join(actions))
    
    def _create_test_group(self, group_id: str, commit_count: int, message: str) -> CommitGroup:
        """Helper to create test commit groups."""
        commits = []
        for i in range(commit_count):
            commit = Commit(
                hash=f"hash{i}",
                short_hash=f"short{i}",
                author="Test Author",
                email="test@example.com",
                timestamp=datetime.now(),
                message=f"{message} {i}",
                files=[f"file{i}.py"],
                insertions=10,
                deletions=5,
                diff="test diff",
                parent_hash="parent"
            )
            commits.append(commit)
        
        return CommitGroup(
            id=group_id,
            commits=commits,
            rationale="test rationale",
            suggested_message=message,
            commit_type="feat",
            scope="auth",
            files_touched=set(f"file{i}.py" for i in range(commit_count)),
            total_insertions=commit_count * 10,
            total_deletions=commit_count * 5
        )


class TestEnhancedMessageGeneration(unittest.TestCase):
    """Test enhanced AI message generation."""
    
    def setUp(self):
        self.config = AIConfig(provider="template")
        self.generator = MessageGenerator(self.config)
        self.template_generator = TemplateMessageGenerator()
    
    def test_template_message_generation(self):
        """Test intelligent template message generation."""
        group = CommitGroup(
            id="test",
            commits=[self._create_test_commit("add user authentication")],
            rationale="authentication feature",
            commit_type="feat",
            scope="auth",
            files_touched={"auth.py", "user.py"},
            total_insertions=50,
            total_deletions=10
        )
        
        message = self.template_generator.generate_message(group)
        
        self.assertIn("feat(auth):", message)
        self.assertIn("authentication", message.lower())
    
    def test_fallback_message_generation(self):
        """Test fallback message generation when AI fails."""
        group = CommitGroup(
            id="test",
            commits=[self._create_test_commit("fix bug")],
            rationale="bug fix",
            suggested_message="fix: resolve issue",
            commit_type="fix",
            files_touched={"app.py"},
            total_insertions=5,
            total_deletions=2
        )
        
        # Mock AI provider to fail
        with patch.object(self.generator.provider, 'generate_commit_message', side_effect=Exception("AI failed")):
            message = self.generator.generate_message(group)
            self.assertEqual(message, "fix: resolve issue")
    
    def test_feature_name_extraction(self):
        """Test extraction of feature names from commit messages."""
        combined_messages = "add user authentication implement login system"
        feature = self.template_generator._extract_feature_name(combined_messages)
        
        self.assertIn(feature, ["user", "authentication", "login", "system"])
    
    def _create_test_commit(self, message: str) -> Commit:
        """Helper to create test commits."""
        return Commit(
            hash="testhash",
            short_hash="test",
            author="Test Author",
            email="test@example.com",
            timestamp=datetime.now(),
            message=message,
            files=["test.py"],
            insertions=10,
            deletions=5,
            diff="test diff",
            parent_hash="parent"
        )


class TestPerformanceOptimizations(unittest.TestCase):
    """Test performance optimization features."""
    
    def setUp(self):
        self.optimizer = PerformanceOptimizer(max_commits=50, timeout_seconds=10)
    
    def test_performance_timing(self):
        """Test performance timing functionality."""
        self.optimizer.start_timer()
        import time
        time.sleep(0.1)
        
        elapsed = self.optimizer.get_elapsed_time()
        self.assertGreater(elapsed, 0.05)
        self.assertLess(elapsed, 0.2)
    
    def test_git_command_optimization(self):
        """Test git command optimization for large repositories."""
        cmd = ["git", "log", "--oneline"]
        optimized = self.optimizer.optimize_git_command(cmd, large_repo=True)
        
        self.assertIn("--max-count", optimized)
        self.assertIn("--no-merges", optimized)
    
    def test_repository_analysis(self):
        """Test repository size analysis."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="1500\n"
            )
            
            size_info = RepositoryAnalyzer.get_repository_size()
            self.assertTrue(size_info['is_large'])
    
    def test_fast_mode_determination(self):
        """Test determination of when to use fast mode."""
        self.assertTrue(self.optimizer.should_use_fast_mode(100))
        self.assertFalse(self.optimizer.should_use_fast_mode(10))


class TestEnhancedGrouping(unittest.TestCase):
    """Test enhanced grouping algorithms."""
    
    def setUp(self):
        self.config = GroupingConfig()
        self.engine = GroupingEngine(self.config)
    
    def test_commit_type_detection(self):
        """Test intelligent commit type detection."""
        commits = [
            self._create_test_commit("add new feature"),
            self._create_test_commit("implement user auth")
        ]
        messages = ["add new feature", "implement user auth"]
        
        detected_type = self.engine._detect_commit_type(commits, messages)
        self.assertEqual(detected_type, "feat")
    
    def test_scope_detection(self):
        """Test scope detection from file paths."""
        files = {"auth/login.py", "auth/user.py", "auth/token.py"}
        scope = self.engine._detect_scope(files)
        self.assertEqual(scope, "auth")
    
    def test_time_span_calculation(self):
        """Test time span calculation for commit groups."""
        now = datetime.now()
        commits = [
            Commit(
                hash="1", short_hash="1", author="test", email="test@example.com",
                timestamp=now, message="first", files=[], insertions=0, deletions=0,
                diff="", parent_hash=""
            ),
            Commit(
                hash="2", short_hash="2", author="test", email="test@example.com",
                timestamp=now.replace(hour=now.hour+1), message="second", files=[], 
                insertions=0, deletions=0, diff="", parent_hash=""
            )
        ]
        
        time_span = self.engine._calculate_time_span_for_group(commits)
        self.assertIn("hour", time_span)
    
    def _create_test_commit(self, message: str) -> Commit:
        """Helper to create test commits."""
        return Commit(
            hash="testhash",
            short_hash="test",
            author="Test Author",
            email="test@example.com",
            timestamp=datetime.now(),
            message=message,
            files=["test.py"],
            insertions=10,
            deletions=5,
            diff="test diff",
            parent_hash="parent"
        )


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete workflows."""
    
    def test_zero_friction_workflow(self):
        """Test the complete zero-friction workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # This would be a more complex integration test
            # that sets up a real git repository and tests the full workflow
            pass
    
    def test_large_repository_handling(self):
        """Test handling of large repositories."""
        # Mock a large repository scenario
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="2000\n")
            
            analyzer = RepositoryAnalyzer()
            size_info = analyzer.get_repository_size()
            
            self.assertTrue(size_info['is_large'])
            self.assertTrue(analyzer.should_use_performance_mode(100))


if __name__ == '__main__':
    unittest.main()