#!/usr/bin/env python3
"""
End-to-end tests for hunk application, grouping fidelity, remaining changes,
and attribution toggles. These tests exercise the real git patch path.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, AttributionConfig
from git_smart_squash.diff_parser import parse_diff, Hunk


class TestE2EHunkApplication(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.tempdir)

        # Initialize repo and ensure main exists
        subprocess.run(['git', 'init'], check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)
        # Create main branch explicitly for determinism
        subprocess.run(['git', 'checkout', '-b', 'main'], check=True)

        with open('README.md', 'w') as f:
            f.write('# Test Repo\n')
        subprocess.run(['git', 'add', 'README.md'], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'Initial commit'], check=True)

        # Create feature branch with three files (one without trailing newline)
        subprocess.run(['git', 'checkout', '-b', 'feature/apply'], check=True)

        with open('file1.py', 'w') as f:
            f.write('def f1():\n    return 1\n')

        # file2 without trailing newline and with simple content
        with open('file2.txt', 'wb') as f:
            f.write(b'line1\nline2')  # no trailing \n

        with open('extra.py', 'w') as f:
            f.write('def extra():\n    return 42\n')

        subprocess.run(['git', 'add', '.'], check=True)
        # One messy commit to produce a clear diff vs main
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'WIP: add three files'], check=True)

        # Prepare CLI with defaults
        self.cli = GitSmartSquashCLI()
        self.cli.config = Config(ai=AIConfig(provider='local', model='devstral'),
                                 hunks=HunkConfig(),
                                 attribution=AttributionConfig(enabled=True),
                                 auto_apply=False)

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tempdir)

    def _hunks_by_file(self):
        diff = self.cli.get_full_diff('main')
        self.assertIsInstance(diff, str)
        hunks = parse_diff(diff)
        self.assertGreaterEqual(len(hunks), 3)
        by_file = {}
        for h in hunks:
            by_file.setdefault(h.file_path, []).append(h)
        return by_file, hunks, diff

    def test_apply_commit_plan_grouping_and_remaining_with_attribution(self):
        by_file, hunks, full_diff = self._hunks_by_file()

        # Build a plan: commit for file1.py, commit for file2.txt, leave extra.py as remaining
        file1_hunk_ids = [h.id for h in by_file.get('file1.py', [])]
        file2_hunk_ids = [h.id for h in by_file.get('file2.txt', [])]
        self.assertTrue(file1_hunk_ids)
        self.assertTrue(file2_hunk_ids)

        plan = [
            {
                'message': 'feat: commit file1',
                'hunk_ids': file1_hunk_ids,
                'rationale': 'Group file1 changes'
            },
            {
                'message': 'chore: commit file2',
                'hunk_ids': file2_hunk_ids,
                'rationale': 'Group file2 changes'
            },
        ]

        # Apply with attribution enabled
        self.cli.apply_commit_plan(plan, hunks, full_diff, base_branch='main', no_attribution=False)

        # Inspect commits (latest three commits should be: remaining, chore file2, feat file1)
        log = subprocess.run(['git', 'log', '--oneline', '-3'], capture_output=True, text=True, check=True).stdout
        self.assertIn('feat: commit file1', log)
        self.assertIn('chore: commit file2', log)
        self.assertIn('chore: remaining uncommitted changes', log)

        # Verify attribution footer present in planned commits
        show1 = subprocess.run(['git', 'show', '-s', '--format=%B', 'HEAD~1'], capture_output=True, text=True, check=True).stdout
        show2 = subprocess.run(['git', 'show', '-s', '--format=%B', 'HEAD~2'], capture_output=True, text=True, check=True).stdout
        self.assertIn('Made with git-smart-squash', show1)
        self.assertIn('Made with git-smart-squash', show2)

        # Verify files per commit
        # HEAD is remaining (extra.py)
        head_files = subprocess.run(['git', 'show', '--name-only', '--pretty=', 'HEAD'], capture_output=True, text=True, check=True).stdout
        self.assertIn('extra.py', head_files)
        self.assertNotIn('file1.py', head_files)
        self.assertNotIn('file2.txt', head_files)

        # HEAD~1 is chore: commit file2
        head1_files = subprocess.run(['git', 'show', '--name-only', '--pretty=', 'HEAD~1'], capture_output=True, text=True, check=True).stdout
        self.assertIn('file2.txt', head1_files)
        self.assertNotIn('file1.py', head1_files)
        self.assertNotIn('extra.py', head1_files)

        # HEAD~2 is feat: commit file1
        head2_files = subprocess.run(['git', 'show', '--name-only', '--pretty=', 'HEAD~2'], capture_output=True, text=True, check=True).stdout
        self.assertIn('file1.py', head2_files)
        self.assertNotIn('file2.txt', head2_files)
        self.assertNotIn('extra.py', head2_files)

    def test_no_attribution_toggle(self):
        # Create a fresh feature branch for no-attribution scenario
        subprocess.run(['git', 'checkout', 'main'], check=True)
        subprocess.run(['git', 'checkout', '-b', 'feature/noattr'], check=True)

        with open('only1.py', 'w') as f:
            f.write('def only():\n    return 7\n')
        subprocess.run(['git', 'add', 'only1.py'], check=True)
        subprocess.run(['git', 'commit', '--no-verify', '-m', 'WIP: only1'], check=True)

        # Compute hunks for this branch
        diff = self.cli.get_full_diff('main')
        hunks = parse_diff(diff)
        ids = [h.id for h in hunks if h.file_path == 'only1.py']
        self.assertTrue(ids)

        plan = [{
            'message': 'feat: only1 (no attribution)',
            'hunk_ids': ids,
            'rationale': 'No attribution test'
        }]

        self.cli.apply_commit_plan(plan, hunks, diff, base_branch='main', no_attribution=True)

        msg = subprocess.run(['git', 'show', '-s', '--format=%B', 'HEAD'], capture_output=True, text=True, check=True).stdout
        self.assertIn('feat: only1 (no attribution)', msg)
        self.assertNotIn('Made with git-smart-squash', msg)


if __name__ == '__main__':
    unittest.main()
