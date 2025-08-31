"""Git diff helpers."""

import os
import subprocess
from typing import Optional

def get_full_diff(base_branch: str, console=None) -> Optional[str]:
    """Get the full diff between a base and HEAD.

    Robustly resolves the base reference across common variants:
    - <base>
    - origin/<base>
    - master / origin/master
    - develop / origin/develop
    Falls back to the repository's first commit if none of the above exist.
    Returns None if there are no changes.
    """
    env = {**os.environ, 'GIT_PAGER': 'cat', 'COLUMNS': '999999'}

    def _ref_exists(ref: str) -> bool:
        res = subprocess.run(['git', 'rev-parse', '--verify', '--quiet', ref], capture_output=True)
        return res.returncode == 0

    # Ensure we are in a git repo
    subprocess.run(['git', 'rev-parse', '--git-dir'], check=True, capture_output=True)

    # Build candidate bases
    candidates = [
        base_branch,
        f'origin/{base_branch}',
        'master', 'origin/master',
        'develop', 'origin/develop',
    ]

    base_ref = None
    for cand in candidates:
        if _ref_exists(cand):
            base_ref = cand
            if console and cand != base_branch:
                console.print(f"[yellow]Using {cand} as base reference[/yellow]")
            break

    # Final fallback to the first commit
    if base_ref is None:
        first = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], capture_output=True, text=True)
        first_commit = first.stdout.strip().splitlines()[0] if first.stdout.strip() else None
        if first_commit:
            base_ref = first_commit
            if console:
                console.print("[yellow]Base not found; using repository root commit as base[/yellow]")
        else:
            # No commits; nothing to diff
            return None

    # Produce diff
    result = subprocess.run(
        ['git', '-c', 'core.pager=', 'diff', '--no-textconv', f'{base_ref}...HEAD'],
        capture_output=True, text=True, check=True, env=env
    )
    if not result.stdout.strip():
        return None
    return result.stdout
