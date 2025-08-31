#!/usr/bin/env python3
"""
Tests that simulate a patch apply failure and verify working directory
and staging restoration (directly via internal helper).
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from git_smart_squash.hunk_applicator import _apply_patch_with_git


class TestApplyFailureRestoration(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.old = os.getcwd()
        os.chdir(self.tempdir)
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)

        with open('target.txt', 'w') as f:
            f.write('one\n two\nthree\n')
        subprocess.run(['git', 'add', 'target.txt'], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'initial'], check=True)

        with open('target.txt', 'r') as f:
            self.original = f.read()

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.tempdir)

    def test_failed_apply_restores_state(self):
        # Intentionally malformed/incorrect patch that won't apply
        bad_patch = (
            'diff --git a/target.txt b/target.txt\n'
            '--- a/target.txt\n'
            '+++ b/target.txt\n'
            '@@ -1,1 +1,1 @@\n'
            '-zzz\n'
            '+yyy\n'
        )

        # Ensure there are no staged changes before
        before = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True, check=True).stdout
        self.assertEqual(before.strip(), '')

        ok = _apply_patch_with_git(bad_patch)
        self.assertFalse(ok)

        # File should be unchanged
        with open('target.txt', 'r') as f:
            after = f.read()
        self.assertEqual(after, self.original)

        # Staging should remain empty
        after_cached = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True, check=True).stdout
        self.assertEqual(after_cached.strip(), '')


if __name__ == '__main__':
    unittest.main()

