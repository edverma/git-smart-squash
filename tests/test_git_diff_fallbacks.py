#!/usr/bin/env python3
"""
Tests for utils.git_diff.get_full_diff fallback behavior.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from git_smart_squash.utils.git_diff import get_full_diff


class TestGitDiffFallbacks(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.old = os.getcwd()
        os.chdir(self.tempdir)
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tempdir)

    def _commit_file(self, path: str, content: str, msg: str):
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d)
        with open(path, 'w') as f:
            f.write(content)
        subprocess.run(['git', 'add', path], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', msg], check=True)

    def test_fallback_to_master_when_main_missing(self):
        # Ensure initial branch is master for this repo
        subprocess.run(['git', 'checkout', '-b', 'master'], check=True)
        self._commit_file('a.txt', 'a\n', 'initial')

        # Create feature with changes
        subprocess.run(['git', 'checkout', '-b', 'feature'], check=True)
        self._commit_file('b.txt', 'b\n', 'feat: add b')

        # Ask for main which doesn't exist; should fall back to master
        diff = get_full_diff('main')
        self.assertIsInstance(diff, str)
        self.assertIn('diff --git', diff)

    def test_fallback_to_first_commit_when_no_known_bases(self):
        # Make initial commit on main
        subprocess.run(['git', 'checkout', '-b', 'main'], check=True)
        self._commit_file('base.txt', 'base\n', 'base')
        # Add another commit to create diff content
        self._commit_file('c.txt', 'c\n', 'feat: add c')

        # Request a totally invalid base to trigger final fallback
        diff = get_full_diff('totally-nonexistent-base')
        self.assertIsInstance(diff, str)
        # Either returns None (no changes) or a diff string; we expect diff because we added commits
        if diff is not None:
            self.assertIn('diff --git', diff)


if __name__ == '__main__':
    unittest.main()

