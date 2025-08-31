"""Git diff helpers."""

import os
import subprocess
from typing import Optional

def get_full_diff(base_branch: str, console=None) -> Optional[str]:
    """Get the full diff between a base and HEAD with graceful fallbacks.

    Call pattern intentionally keeps a simple sequence to align with tests:
    - Ensure repo
    - Try diff with <base>
    - Fallback: origin/<base>, master, origin/master, develop, origin/develop
    - Final fallback: first commit (if available)
    Returns None if the diff is empty (whitespace only).
    """
    env = {**os.environ, 'GIT_PAGER': 'cat', 'COLUMNS': '999999'}

    try:
        # Ensure we are inside a git repository
        subprocess.run(['git', 'rev-parse', '--git-dir'], check=True, capture_output=True)

        def _try_diff(ref: str) -> Optional[str]:
            result = subprocess.run(
                ['git', '-c', 'core.pager=', 'diff', '--no-textconv', f'{ref}...HEAD'],
                capture_output=True, text=True, check=True, env=env
            )
            if not result.stdout.strip():
                return None
            return result.stdout

        # 1) Primary base
        try:
            out = _try_diff(base_branch)
            return out
        except subprocess.CalledProcessError as e_primary:
            last_err = e_primary

        # 2) Alternative bases
        for alt_base in [f'origin/{base_branch}', 'master', 'origin/master', 'develop', 'origin/develop']:
            try:
                out = _try_diff(alt_base)
                if out is not None:
                    if console:
                        console.print(f"[yellow]Using {alt_base} as base branch[/yellow]")
                    return out
                else:
                    # Diff empty
                    return None
            except subprocess.CalledProcessError as e_alt:
                last_err = e_alt
                continue

        # 3) Final fallback to first commit
        try:
            first = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], capture_output=True, text=True, check=True)
            first_commit = first.stdout.strip().splitlines()[0] if first.stdout.strip() else None
            if first_commit:
                out = _try_diff(first_commit)
                return out
        except subprocess.CalledProcessError as e_first:
            last_err = e_first

        # If we got here, everything failed
        raise Exception(f"Could not get diff from {base_branch}: {getattr(last_err, 'stderr', '')}")

    except subprocess.CalledProcessError as e:
        # Repository not available or other git error
        raise Exception(f"Could not get diff from {base_branch}: {e.stderr}")
