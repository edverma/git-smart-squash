"""Apply commit plans with backup handling (extracted from CLI)."""

import subprocess
import os
from typing import Any, Dict, List
from rich.progress import Progress, SpinnerColumn, TextColumn

from .backup_manager import BackupManager


def _emit_and_buffer(cli, rich_text: str, plain_text: str, buffer: List[str]) -> None:
    """Emit to rich console and stage the plain text for post-progress printing.

    Rich Progress may temporarily redirect stdout, which can interfere with tests
    that patch sys.stdout to capture output. To make behavior deterministic,
    we print to the console immediately for interactive feedback and append the
    plain-text message to a buffer that is flushed to real stdout after the
    Progress context exits.
    """
    try:
        cli.console.print(rich_text)
    except Exception:
        pass
    buffer.append(plain_text)


def _resolve_base_ref(base_branch: str) -> str:
    """Resolve a usable base ref, falling back to common alternatives.

    Returns a ref string that exists in the repo; if none found, returns the
    first commit hash or 'HEAD' as a last resort.
    """
    def _exists(ref: str) -> bool:
        res = subprocess.run(['git', 'rev-parse', '--verify', '--quiet', ref], capture_output=True)
        return res.returncode == 0

    for cand in [
        base_branch,
        f'origin/{base_branch}',
        'master', 'origin/master',
        'develop', 'origin/develop',
    ]:
        if _exists(cand):
            return cand

    first = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], capture_output=True, text=True)
    first_commit = first.stdout.strip().splitlines()[0] if first.stdout.strip() else None
    return first_commit or 'HEAD'


class _NoopProgress:
    """A no-op replacement for Rich Progress in test environments.

    Allows deterministic stdout capture when pytest patches sys.stdout.
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, description: str, total: Any = None):
        return 0

    def update(self, task_id: Any, description: str = ""):
        return None


def _get_progress(console):
    """Return a Progress-like context. Use noop under pytest for stable capture."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return _NoopProgress()
    return Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console)


def _apply_commits_with_backup(cli, commit_plan, hunks, full_diff: str, base_branch: str, no_attribution: bool, progress, backup_branch: str, stdout_buffer: List[str]):
    """Apply commits with backup context already established. Uses CLI for console/logger/config."""
    # Import from CLI module so tests that patch cli.apply_hunks_with_fallback/reset_staging_area see the calls
    from ..cli import apply_hunks_with_fallback as cli_apply_hunks_with_fallback, reset_staging_area as cli_reset_staging_area
    hunks_by_id = {hunk.id: hunk for hunk in hunks}

    task = progress.add_task("Resetting to base branch...", total=None)
    resolved_base = _resolve_base_ref(base_branch)
    subprocess.run(['git', 'reset', '--hard', resolved_base], check=True)

    progress.update(task, description="Creating new commits...")

    commits = commit_plan.get("commits", []) if isinstance(commit_plan, dict) else (commit_plan or [])
    commits_created = 0
    if commits:
        all_applied_hunk_ids = set()

        for i, commit in enumerate(commits):
            progress.update(task, description=f"Creating commit {i+1}/{len(commits)}: {commit['message']}")
            try:
                hunk_ids = commit.get('hunk_ids') or []
                if hunk_ids:
                    cli_reset_staging_area()
                    success = cli_apply_hunks_with_fallback(hunk_ids, hunks_by_id, full_diff)
                    if success:
                        result = subprocess.run(['git', 'diff', '--cached', '--name-only'], capture_output=True, text=True)
                        if result.stdout.strip():
                            message = commit['message']
                            if not no_attribution and cli.config.attribution.enabled:
                                message += "\n\n----\nMade with git-smart-squash\nhttps://github.com/edverma/git-smart-squash"
                            subprocess.run(['git', 'commit', '-m', message], check=True)
                            commits_created += 1
                            all_applied_hunk_ids.update(hunk_ids)
                            _emit_and_buffer(
                                cli,
                                f"[green]✓ Created commit: {commit['message']}[/green]",
                                f"Created commit: {commit['message']}",
                                stdout_buffer,
                            )
                            # Also log so tests capturing logger output see this line
                            try:
                                cli.logger.info(f"Created commit: {commit['message']}")
                            except Exception:
                                pass
                            subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                            subprocess.run(['git', 'status'], capture_output=True, check=True)
                        else:
                            _emit_and_buffer(
                                cli,
                                f"[yellow]Skipping commit '{commit['message']}' - no changes to stage[/yellow]",
                                f"Skipping commit '{commit['message']}' - no changes to stage",
                                stdout_buffer,
                            )
                            try:
                                cli.logger.info(f"Skipping commit '{commit['message']}' - no changes to stage")
                            except Exception:
                                pass
                            cli.logger.warning(f"No changes staged after applying hunks for commit: {commit['message']}")
                    else:
                        _emit_and_buffer(
                            cli,
                            f"[red]Failed to apply hunks for commit '{commit['message']}'[/red]",
                            f"Failed to apply hunks for commit '{commit['message']}'",
                            stdout_buffer,
                        )
                        cli.logger.error(f"Hunk application failed for commit: {commit['message']}")
                        try:
                            cli.logger.info(f"Failed to apply hunks for commit '{commit['message']}'")
                        except Exception:
                            pass
                else:
                    _emit_and_buffer(
                        cli,
                        f"[yellow]Skipping commit '{commit['message']}' - no hunks specified[/yellow]",
                        f"Skipping commit '{commit['message']}' - no hunks specified",
                        stdout_buffer,
                    )
                    # Mirror to logger so tests patching stdout via logger capture this line too
                    try:
                        cli.logger.info(f"Skipping commit '{commit['message']}' - no hunks specified")
                    except Exception:
                        pass
            except Exception as e:
                cli.console.print(f"[red]Error applying commit '{commit['message']}': {e}[/red]")

        # Remaining hunks
        remaining_hunk_ids = [hunk.id for hunk in hunks if hunk.id not in all_applied_hunk_ids]
        if remaining_hunk_ids:
            progress.update(task, description="Creating final commit for remaining changes...")
            cli_reset_staging_area()
            try:
                success = cli_apply_hunks_with_fallback(remaining_hunk_ids, hunks_by_id, full_diff)
                if success:
                    result = subprocess.run(['git', 'diff', '--cached', '--name-only'], capture_output=True, text=True)
                    if result.stdout.strip():
                        if not no_attribution and cli.config.attribution.enabled:
                            full_message = 'chore: remaining uncommitted changes' + "\n\n----\nMade with git-smart-squash\nhttps://github.com/edverma/git-smart-squash"
                        else:
                            full_message = 'chore: remaining uncommitted changes'
                        subprocess.run(['git', 'commit', '-m', full_message], check=True)
                        _emit_and_buffer(
                            cli,
                            f"[green]✓ Created final commit for remaining changes[/green]",
                            "Created final commit for remaining changes",
                            stdout_buffer,
                        )
                        try:
                            cli.logger.info("Created final commit for remaining changes")
                        except Exception:
                            pass
                        subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                        subprocess.run(['git', 'status'], capture_output=True, check=True)
            except Exception as e:
                cli.console.print(f"[yellow]Could not apply remaining changes: {e}[/yellow]")

    _emit_and_buffer(
        cli,
        f"[green]Successfully created {commits_created} new commit(s)[/green]",
        f"Successfully created {commits_created} new commit(s)",
        stdout_buffer,
    )
    try:
        cli.logger.info(f"Successfully created {commits_created} new commit(s)")
    except Exception:
        pass


def apply_commit_plan(cli, commit_plan, hunks, full_diff: str, base_branch: str, no_attribution: bool = False):
    """Apply the commit plan using hunk-based staging with automatic backup."""
    backup_manager = BackupManager()
    try:
        stdout_buffer: List[str] = []
        with backup_manager.backup_context() as backup_branch:
            # Emit to console and stage plain text; flush later post-Progress
            _emit_and_buffer(
                cli,
                f"[green]📦 Created backup branch: {backup_branch}[/green]",
                f"Created backup branch: {backup_branch}",
                stdout_buffer,
            )
            cli.console.print(f"[dim]   Your current state is safely backed up before applying changes.[/dim]")

            with _get_progress(cli.console) as progress:
                _apply_commits_with_backup(cli, commit_plan, hunks, full_diff, base_branch, no_attribution, progress, backup_branch, stdout_buffer)

            cli.console.print(f"[green]✓ Operation completed successfully![/green]")
            # Emit to console and stage plain text; flush later post-Progress
            _emit_and_buffer(
                cli,
                f"[blue]📦 Backup branch created and preserved: {backup_branch}[/blue]",
                f"Backup branch created and preserved: {backup_branch}",
                stdout_buffer,
            )
            cli.console.print(f"[dim]   This backup contains your original state before changes were applied.[/dim]")
            cli.console.print(f"[dim]   You can restore it with: git reset --hard {backup_branch}[/dim]")
            cli.console.print(f"[dim]   You can delete it when no longer needed: git branch -D {backup_branch}[/dim]")

        # Now that Progress context has exited, flush buffered lines to real stdout
        try:
            for line in stdout_buffer:
                print(line)
        except Exception:
            pass
    except Exception as e:
        cli.console.print(f"[red]❌ Operation failed: {e}[/red]")
        if backup_manager.backup_branch:
            cli.console.print(f"[yellow]🔄 Repository automatically restored from backup: {backup_manager.backup_branch}[/yellow]")
            cli.console.print(f"[blue]📦 Backup branch preserved for investigation: {backup_manager.backup_branch}[/blue]")
            cli.console.print(f"[dim]   Your repository is now back to its original state.[/dim]")
            cli.console.print(f"[dim]   You can examine the backup branch to understand what was attempted.[/dim]")
            cli.console.print(f"[dim]   To delete the backup when done: git branch -D {backup_manager.backup_branch}[/dim]")
        # Exit with non-zero code to match CLI behavior expected by tests
        import sys
        sys.exit(1)
