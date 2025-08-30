"""Apply commit plans with backup handling (extracted from CLI)."""

import subprocess
from typing import Any, Dict, List
from rich.progress import Progress, SpinnerColumn, TextColumn

from .backup_manager import BackupManager


def _apply_commits_with_backup(cli, commit_plan, hunks, full_diff: str, base_branch: str, no_attribution: bool, progress, backup_branch: str):
    """Apply commits with backup context already established. Uses CLI for console/logger/config."""
    # Import from CLI module so tests that patch cli.apply_hunks_with_fallback/reset_staging_area see the calls
    from ..cli import apply_hunks_with_fallback as cli_apply_hunks_with_fallback, reset_staging_area as cli_reset_staging_area
    hunks_by_id = {hunk.id: hunk for hunk in hunks}

    task = progress.add_task("Resetting to base branch...", total=None)
    subprocess.run(['git', 'reset', '--hard', base_branch], check=True)

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
                            cli.console.print(f"[green]✓ Created commit: {commit['message']}[/green]")
                            subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                            subprocess.run(['git', 'status'], capture_output=True, check=True)
                        else:
                            cli.console.print(f"[yellow]Skipping commit '{commit['message']}' - no changes to stage[/yellow]")
                            cli.logger.warning(f"No changes staged after applying hunks for commit: {commit['message']}")
                    else:
                        cli.console.print(f"[red]Failed to apply hunks for commit '{commit['message']}'[/red]")
                        cli.logger.error(f"Hunk application failed for commit: {commit['message']}")
                else:
                    cli.console.print(f"[yellow]Skipping commit '{commit['message']}' - no hunks specified[/yellow]")
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
                        cli.console.print(f"[green]✓ Created final commit for remaining changes[/green]")
                        subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                        subprocess.run(['git', 'status'], capture_output=True, check=True)
            except Exception as e:
                cli.console.print(f"[yellow]Could not apply remaining changes: {e}[/yellow]")

    cli.console.print(f"[green]Successfully created {commits_created} new commit(s)[/green]")


def apply_commit_plan(cli, commit_plan, hunks, full_diff: str, base_branch: str, no_attribution: bool = False):
    """Apply the commit plan using hunk-based staging with automatic backup."""
    backup_manager = BackupManager()
    try:
        with backup_manager.backup_context() as backup_branch:
            cli.console.print(f"[green]📦 Created backup branch: {backup_branch}[/green]")
            cli.console.print(f"[dim]   Your current state is safely backed up before applying changes.[/dim]")

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=cli.console) as progress:
                _apply_commits_with_backup(cli, commit_plan, hunks, full_diff, base_branch, no_attribution, progress, backup_branch)

            cli.console.print(f"[green]✓ Operation completed successfully![/green]")
            cli.console.print(f"[blue]📦 Backup branch created and preserved: {backup_branch}[/blue]")
            cli.console.print(f"[dim]   This backup contains your original state before changes were applied.[/dim]")
            cli.console.print(f"[dim]   You can restore it with: git reset --hard {backup_branch}[/dim]")
            cli.console.print(f"[dim]   You can delete it when no longer needed: git branch -D {backup_branch}[/dim]")
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
