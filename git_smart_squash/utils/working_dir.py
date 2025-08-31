"""Working directory status utilities."""

import subprocess
from typing import Dict, Any

from ..logger import get_logger

logger = get_logger()


def check_clean() -> Dict[str, Any]:
    """Return working directory status using porcelain format without trimming columns."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'], capture_output=True, text=True, check=True
        )

        status_lines = result.stdout.splitlines() if result.stdout else []

        staged_files = []
        unstaged_files = []
        untracked_files = []

        for line in status_lines:
            if len(line) >= 2:
                index_status = line[0]
                worktree_status = line[1]
                file_path = line[3:] if len(line) > 3 else ""

                if index_status != ' ' and index_status != '?':
                    staged_files.append(file_path)
                if worktree_status != ' ' and worktree_status != '?':
                    unstaged_files.append(file_path)
                if index_status == '?' and worktree_status == '?':
                    untracked_files.append(file_path)

        is_clean = len(staged_files) == 0 and len(unstaged_files) == 0 and len(untracked_files) == 0

        if is_clean:
            message = "Working directory is clean"
        else:
            parts = []
            if staged_files:
                parts.append(f"{len(staged_files)} staged file(s)")
            if unstaged_files:
                parts.append(f"{len(unstaged_files)} unstaged change(s)")
            if untracked_files:
                parts.append(f"{len(untracked_files)} untracked file(s)")
            message = f"Working directory has uncommitted changes: {', '.join(parts)}"

        return {
            "is_clean": is_clean,
            "staged_files": staged_files,
            "unstaged_files": unstaged_files,
            "untracked_files": untracked_files,
            "message": message,
        }

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check working directory status: {e}")
        return {
            "is_clean": False,
            "staged_files": [],
            "unstaged_files": [],
            "untracked_files": [],
            "message": "Unable to determine working directory status",
        }


def display_help(console, status_info: Dict[str, Any]) -> None:
    """Render helpful guidance for cleaning the working directory."""
    console.print(f"[red]❌ Cannot proceed: {status_info['message']}[/red]")
    console.print("[yellow]Git Smart Squash requires a clean working directory to operate safely.[/yellow]")
    console.print("")

    if status_info['staged_files']:
        console.print("[bold]Staged files (ready to commit):[/bold]")
        for file_path in status_info['staged_files'][:10]:
            console.print(f"  📝 {file_path}")
        if len(status_info['staged_files']) > 10:
            console.print(f"  ... and {len(status_info['staged_files']) - 10} more")
        console.print("")
        console.print("[dim]To handle staged files:[/dim]")
        console.print("[dim]  • Commit them: git commit -m \"Your message\"[/dim]")
        console.print("[dim]  • Unstage them: git reset HEAD[/dim]")
        console.print("")

    if status_info['unstaged_files']:
        console.print("[bold]Modified files (unstaged):[/bold]")
        for file_path in status_info['unstaged_files'][:10]:
            console.print(f"  📄 {file_path}")
        if len(status_info['unstaged_files']) > 10:
            console.print(f"  ... and {len(status_info['unstaged_files']) - 10} more")
        console.print("")
        console.print("[dim]To handle unstaged changes:[/dim]")
        console.print("[dim]  • Commit them: git add . && git commit -m \"Your message\"[/dim]")
        console.print("[dim]  • Stash them: git stash[/dim]")
        console.print("[dim]  • Discard them: git checkout .[/dim]")
        console.print("")

    if status_info['untracked_files']:
        console.print("[bold]Untracked files:[/bold]")
        for file_path in status_info['untracked_files'][:10]:
            console.print(f"  ❓ {file_path}")
        if len(status_info['untracked_files']) > 10:
            console.print(f"  ... and {len(status_info['untracked_files']) - 10} more")
        console.print("")
        console.print("[dim]To handle untracked files:[/dim]")
        console.print("[dim]  • Add and commit them: git add . && git commit -m \"Your message\"[/dim]")
        console.print("[dim]  • Remove them: rm <filename> (be careful!)[/dim]")
        console.print("[dim]  • Ignore them: add to .gitignore[/dim]")
        console.print("")

    console.print("[green]💡 Once your working directory is clean, run git-smart-squash again.[/green]")

