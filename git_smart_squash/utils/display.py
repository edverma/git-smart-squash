"""Display helpers for commit plans."""

from typing import Any, Dict, List
from rich.panel import Panel


def display_commit_plan(console, commit_plan):
    """Render commit plan panels. Accepts list or object with 'commits'."""
    console.print("\n[bold]Proposed Commit Structure:[/bold]")

    if isinstance(commit_plan, dict) and "commits" in commit_plan:
        commits: List[Dict[str, Any]] = commit_plan.get("commits", [])
    else:
        commits = commit_plan or []

    for i, commit in enumerate(commits, 1):
        panel_content: List[str] = []
        message = commit.get('message', '(no message)')
        panel_content.append(f"[bold]Message:[/bold] {message}")

        if commit.get('hunk_ids'):
            hunk_ids = commit['hunk_ids']
            hunks_by_file: Dict[str, List[str]] = {}
            for hunk_id in hunk_ids:
                if ':' in hunk_id:
                    file_path = hunk_id.split(':')[0]
                    hunks_by_file.setdefault(file_path, []).append(hunk_id)
                else:
                    hunks_by_file.setdefault('unknown', []).append(hunk_id)

            console_lines = ["[bold]Hunks:[/bold]"]
            for file_path, file_hunks in hunks_by_file.items():
                descr = []
                for hunk_id in file_hunks:
                    if ':' in hunk_id:
                        line_range = hunk_id.split(':')[1]
                        descr.append(f"lines {line_range}")
                    else:
                        descr.append(hunk_id)
                console_lines.append(f"  • {file_path}: {', '.join(descr)}")
            panel_content.extend(console_lines)
        elif commit.get('files'):
            panel_content.append(f"[bold]Files:[/bold] {', '.join(commit['files'])}")

        rationale = commit.get('rationale', '(no rationale provided)')
        panel_content.append(f"[bold]Rationale:[/bold] {rationale}")

        console.print(Panel("\n".join(panel_content), title=f"Commit #{i}", border_style="blue"))
