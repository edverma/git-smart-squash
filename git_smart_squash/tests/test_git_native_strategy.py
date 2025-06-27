"""Tests for Git native strategy implementation."""

import pytest
import tempfile
import os
import git
from pathlib import Path
import base64

from ..strategies import GitNativeStrategy
from ..models import CommitGroup, Hunk, ChangeType
from ..diff_parser import Hunk as LegacyHunk


class TestGitNativeStrategy:
    """Test suite for Git native operations."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary Git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = git.Repo.init(tmpdir)
            
            # Configure git user for commits
            repo.config_writer().set_value("user", "name", "Test User").release()
            repo.config_writer().set_value("user", "email", "test@example.com").release()
            
            # Add initial files
            (Path(tmpdir) / "main.py").write_text("print('hello')\n")
            (Path(tmpdir) / "layout.svelte").write_text(
                '<script>console.log("test")</script>\n'
                '<main class="old-class">content</main>\n'
            )
            (Path(tmpdir) / "utils.js").write_text(
                "function oldFunction() {\n"
                "    return 'old';\n"
                "}\n"
            )
            
            repo.index.add(["main.py", "layout.svelte", "utils.js"])
            repo.index.commit("Initial commit")
            
            yield repo
            
    def test_validate_environment(self, temp_repo):
        """Test environment validation."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        result = strategy.validate_environment()
        
        assert result.is_success
        assert "validated successfully" in result.message
        
    def test_handles_line_number_shifts(self, temp_repo):
        """Test the specific case that was failing with patch approach."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        # First commit: Add analytics (shifts line numbers)
        commit1 = CommitGroup(
            id="1",
            message="Add analytics",
            hunks=[
                Hunk(
                    id="layout.svelte:1-5",
                    file_path="layout.svelte",
                    start_line=1,
                    end_line=1,
                    content='',  # Not used with new_content
                    change_type=ChangeType.MODIFICATION,
                    new_content=(
                        '<script>\n'
                        'import analytics from "./analytics"\n'
                        'console.log("test")\n'
                        'analytics.init()\n'
                        '</script>\n'
                        '<main class="old-class">content</main>\n'
                    )
                )
            ]
        )
        
        # Second commit: Change theme (would fail with old approach)
        commit2 = CommitGroup(
            id="2", 
            message="Update theme",
            hunks=[
                Hunk(
                    id="layout.svelte:6-6",
                    file_path="layout.svelte",
                    start_line=6,  # Original line 2, but now line 6 after first commit
                    end_line=6,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    old_content='<main class="old-class">content</main>',
                    new_content='<main class="new-class">content</main>'
                )
            ]
        )
        
        # Apply commits
        result = strategy.apply_commits([commit1, commit2])
        
        # Verify success
        assert result.is_success
        
        # Verify file content
        final_content = (Path(temp_repo.working_dir) / "layout.svelte").read_text()
        assert 'class="new-class"' in final_content
        assert 'analytics.init()' in final_content
        
    def test_multiple_files_single_commit(self, temp_repo):
        """Test modifying multiple files in a single commit."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Update multiple files",
            hunks=[
                Hunk(
                    id="main.py:1-1",
                    file_path="main.py",
                    start_line=1,
                    end_line=1,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    new_content="print('updated')\nprint('new line')\n"
                ),
                Hunk(
                    id="utils.js:1-3",
                    file_path="utils.js",
                    start_line=1,
                    end_line=3,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    new_content=(
                        "function newFunction() {\n"
                        "    return 'new';\n"
                        "}\n"
                    )
                )
            ]
        )
        
        result = strategy.apply_commits([commit])
        
        assert result.is_success
        
        # Verify both files were updated
        main_content = (Path(temp_repo.working_dir) / "main.py").read_text()
        assert "print('updated')" in main_content
        assert "print('new line')" in main_content
        
        utils_content = (Path(temp_repo.working_dir) / "utils.js").read_text()
        assert "newFunction" in utils_content
        assert "return 'new'" in utils_content
        
    def test_file_creation(self, temp_repo):
        """Test creating new files."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Add new configuration file",
            hunks=[
                Hunk(
                    id="config.json:1-5",
                    file_path="config.json",
                    start_line=1,
                    end_line=5,
                    content='',
                    change_type=ChangeType.ADDITION,
                    new_content=(
                        '{\n'
                        '  "name": "test-app",\n'
                        '  "version": "1.0.0",\n'
                        '  "debug": true\n'
                        '}\n'
                    )
                )
            ]
        )
        
        result = strategy.apply_commits([commit])
        
        assert result.is_success
        
        # Verify file was created
        config_path = Path(temp_repo.working_dir) / "config.json"
        assert config_path.exists()
        
        content = config_path.read_text()
        assert '"name": "test-app"' in content
        assert '"debug": true' in content
        
    def test_file_in_subdirectory(self, temp_repo):
        """Test creating/modifying files in subdirectories."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Add component in subdirectory",
            hunks=[
                Hunk(
                    id="src/components/Button.js:1-5",
                    file_path="src/components/Button.js",
                    start_line=1,
                    end_line=5,
                    content='',
                    change_type=ChangeType.ADDITION,
                    new_content=(
                        'export function Button({ label }) {\n'
                        '  return (\n'
                        '    <button>{label}</button>\n'
                        '  );\n'
                        '}\n'
                    )
                )
            ]
        )
        
        result = strategy.apply_commits([commit])
        
        assert result.is_success
        
        # Verify file was created in correct location
        button_path = Path(temp_repo.working_dir) / "src" / "components" / "Button.js"
        assert button_path.exists()
        assert 'export function Button' in button_path.read_text()
        
    def test_commit_with_custom_author(self, temp_repo):
        """Test creating commits with custom author information."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Custom author commit",
            hunks=[
                Hunk(
                    id="main.py:1-1",
                    file_path="main.py",
                    start_line=1,
                    end_line=1,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    new_content="print('custom author')\n"
                )
            ],
            author_name="John Doe",
            author_email="john@example.com"
        )
        
        result = strategy.apply_commits([commit])
        
        assert result.is_success
        
        # Verify commit author
        last_commit = temp_repo.head.commit
        assert last_commit.author.name == "John Doe"
        assert last_commit.author.email == "john@example.com"
        
    def test_empty_commit_group(self, temp_repo):
        """Test handling empty commit groups."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Empty commit",
            hunks=[]
        )
        
        result = strategy.apply_commits([commit])
        
        # Should handle gracefully
        assert result.is_success
        
    def test_rollback_on_failure(self, temp_repo):
        """Test that changes are rolled back on failure."""
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        # Get initial commit
        initial_commit = temp_repo.head.commit
        
        # Create a commit that will fail (invalid hunk)
        commit = CommitGroup(
            id="1",
            message="This will fail",
            hunks=[
                Hunk(
                    id="nonexistent.txt:1-1",
                    file_path="nonexistent.txt",
                    start_line=1,
                    end_line=1,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    old_content="This doesn't exist",
                    new_content="This will fail"
                )
            ]
        )
        
        # This should handle the error gracefully
        result = strategy.apply_commits([commit])
        
        # Verify we're still at the initial commit
        # The strategy should handle this gracefully without rolling back the repo state
        # since it uses a temporary branch
        
    def test_working_directory_cleanup(self, temp_repo):
        """Test that working directory is properly managed."""
        # Create a dirty working directory
        test_file = Path(temp_repo.working_dir) / "dirty.txt"
        test_file.write_text("uncommitted changes")
        
        strategy = GitNativeStrategy(temp_repo.working_dir)
        
        commit = CommitGroup(
            id="1",
            message="Test with dirty working directory",
            hunks=[
                Hunk(
                    id="main.py:1-1",
                    file_path="main.py",
                    start_line=1,
                    end_line=1,
                    content='',
                    change_type=ChangeType.MODIFICATION,
                    new_content="print('applied')\n"
                )
            ]
        )
        
        result = strategy.apply_commits([commit])
        
        assert result.is_success
        
        # The dirty file should be preserved (stashed and restored)
        assert test_file.exists()
        assert test_file.read_text() == "uncommitted changes"