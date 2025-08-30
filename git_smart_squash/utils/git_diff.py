"""Git diff helpers."""

import os
import subprocess
from typing import Optional

def get_full_diff(base_branch: str, console=None) -> Optional[str]:
    """Get the full diff between base branch and current branch with no pager wrapping."""
    env = {**os.environ, 'GIT_PAGER': 'cat', 'COLUMNS': '999999'}
    try:
        subprocess.run(['git', 'rev-parse', '--git-dir'], check=True, capture_output=True)

        result = subprocess.run(
            ['git', '-c', 'core.pager=', 'diff', '--no-textconv', f'{base_branch}...HEAD'],
            capture_output=True, text=True, check=True, env=env
        )
        if not result.stdout.strip():
            return None
        return result.stdout
    except subprocess.CalledProcessError as e:
        if 'unknown revision' in e.stderr:
            for alt_base in [f'origin/{base_branch}', 'develop', 'origin/develop']:
                try:
                    result = subprocess.run(
                        ['git', '-c', 'core.pager=', 'diff', '--no-textconv', f'{alt_base}...HEAD'],
                        capture_output=True, text=True, check=True, env=env
                    )
                    if result.stdout.strip():
                        if console:
                            console.print(f"[yellow]Using {alt_base} as base branch[/yellow]")
                        return result.stdout
                except subprocess.CalledProcessError:
                    continue
        raise Exception(f"Could not get diff from {base_branch}: {e.stderr}")

