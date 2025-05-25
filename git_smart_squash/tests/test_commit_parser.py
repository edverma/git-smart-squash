"""Tests for commit parser functionality."""

import pytest
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock
from git_smart_squash.analyzer.commit_parser import GitCommitParser
from git_smart_squash.models import Commit


class TestGitCommitParser:
    """Test cases for GitCommitParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = GitCommitParser(".")
    
    @patch('subprocess.run')
    def test_get_commits_between_success(self, mock_run):
        """Test successful commit parsing."""
        # Mock git rev-list output
        mock_run.return_value.stdout = "abc123\ndef456\n"
        mock_run.return_value.returncode = 0
        
        # Mock individual commit parsing
        with patch.object(self.parser, '_parse_commit') as mock_parse:
            commit1 = Commit(
                hash="abc123", short_hash="abc123", author="John Doe",
                email="john@example.com", timestamp=datetime.now(),
                message="feat: add feature", files=["file1.py"],
                insertions=10, deletions=5, diff="diff content",
                parent_hash="parent123"
            )
            commit2 = Commit(
                hash="def456", short_hash="def456", author="Jane Doe",
                email="jane@example.com", timestamp=datetime.now(),
                message="fix: bug fix", files=["file2.py"],
                insertions=3, deletions=1, diff="diff content 2",
                parent_hash="abc123"
            )
            mock_parse.side_effect = [commit1, commit2]
            
            commits = self.parser.get_commits_between("main", "HEAD")
            
            assert len(commits) == 2
            assert commits[0].hash == "abc123"
            assert commits[1].hash == "def456"
    
    @patch('subprocess.run')
    def test_get_commits_between_no_commits(self, mock_run):
        """Test when no commits are found."""
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        
        commits = self.parser.get_commits_between("main", "HEAD")
        assert commits == []
    
    @patch('subprocess.run')
    def test_parse_commit_success(self, mock_run):
        """Test successful individual commit parsing."""
        # Mock git show output for metadata
        metadata_output = "abc123def|abc123d|John Doe|john@example.com|1640995200|feat: add feature|parent123"
        mock_run.return_value.stdout = metadata_output
        mock_run.return_value.returncode = 0
        
        # Mock file stats and diff
        with patch.object(self.parser, '_get_commit_stats') as mock_stats, \
             patch.object(self.parser, '_get_commit_diff') as mock_diff:
            mock_stats.return_value = (["file1.py", "file2.py"], 10, 5)
            mock_diff.return_value = "diff content"
            
            commit = self.parser._parse_commit("abc123def")
            
            assert commit is not None
            assert commit.hash == "abc123def"
            assert commit.short_hash == "abc123d"
            assert commit.author == "John Doe"
            assert commit.message == "feat: add feature"
            assert commit.files == ["file1.py", "file2.py"]
            assert commit.insertions == 10
            assert commit.deletions == 5
    
    @patch('subprocess.run')
    def test_get_commit_stats(self, mock_run):
        """Test commit statistics parsing."""
        # Mock file list output
        files_output = "file1.py\nfile2.py\nfile3.js\n"
        
        # Mock stats output
        stats_output = """file1.py | 5 +++--
file2.py | 3 +++
file3.js | 2 --
3 files changed, 8 insertions(+), 4 deletions(-)"""
        
        mock_run.side_effect = [
            MagicMock(stdout=files_output, returncode=0),  # file list
            MagicMock(stdout=stats_output, returncode=0)   # stats
        ]
        
        files, insertions, deletions = self.parser._get_commit_stats("abc123")
        
        assert files == ["file1.py", "file2.py", "file3.js"]
        assert insertions == 8
        assert deletions == 4
    
    @patch('subprocess.run')
    def test_is_git_repo_true(self, mock_run):
        """Test git repository detection - positive case."""
        mock_run.return_value.returncode = 0
        assert self.parser.is_git_repo() is True
    
    @patch('subprocess.run')
    def test_is_git_repo_false(self, mock_run):
        """Test git repository detection - negative case."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        assert self.parser.is_git_repo() is False
    
    @patch('subprocess.run')
    def test_get_current_branch(self, mock_run):
        """Test current branch detection."""
        mock_run.return_value.stdout = "feature-branch\n"
        mock_run.return_value.returncode = 0
        
        branch = self.parser.get_current_branch()
        assert branch == "feature-branch"
    
    @patch('subprocess.run')
    def test_get_default_base_branch(self, mock_run):
        """Test default base branch detection."""
        # Mock successful check for 'main' branch
        mock_run.return_value.returncode = 0
        
        branch = self.parser.get_default_base_branch()
        assert branch == "main"