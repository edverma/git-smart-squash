"""Simplified command-line interface for Git Smart Squash."""

import argparse
import sys
import subprocess
import json
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .simple_config import ConfigManager
from .ai.providers.simple_unified import UnifiedAIProvider
from .diff_parser import parse_diff, Hunk
from .hunk_applicator import apply_hunks_with_fallback, reset_staging_area


class GitSmartSquashCLI:
    """Simplified CLI for git smart squash."""
    
    def __init__(self):
        self.console = Console()
        self.config_manager = ConfigManager()
        self.config = None
    
    def main(self):
        """Main entry point for the CLI."""
        parser = self.create_parser()
        args = parser.parse_args()
        
        try:
            # Load configuration
            self.config = self.config_manager.load_config(args.config)
            
            # Override config with command line arguments
            if args.ai_provider:
                self.config.ai.provider = args.ai_provider
                # If provider is changed but no model specified, use provider default
                if not args.model:
                    self.config.ai.model = self.config_manager._get_default_model(args.ai_provider)
            if args.model:
                self.config.ai.model = args.model
            
            # Run the simplified smart squash
            self.run_smart_squash(args)
                
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the simplified argument parser."""
        parser = argparse.ArgumentParser(
            prog='git-smart-squash',
            description='AI-powered git commit reorganization for clean PR reviews'
        )
        
        parser.add_argument(
            '--base',
            default='main',
            help='Base branch to compare against (default: main)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show proposed commit structure without applying'
        )
        
        parser.add_argument(
            '--ai-provider',
            choices=['openai', 'anthropic', 'local', 'gemini'],
            help='AI provider to use'
        )
        
        parser.add_argument(
            '--model',
            help='AI model to use'
        )
        
        parser.add_argument(
            '--config',
            help='Path to configuration file'
        )
        
        parser.add_argument(
            '--yes', '-y',
            action='store_true',
            help='Automatically accept the generated commit plan without confirmation'
        )
        
        return parser
    
    def run_smart_squash(self, args):
        """Run the simplified smart squash operation."""
        try:
            # Ensure config is loaded
            if self.config is None:
                self.config = self.config_manager.load_config()
            
            # 1. Get the full diff between base branch and current branch
            full_diff = self.get_full_diff(args.base)
            if not full_diff:
                self.console.print("[yellow]No changes found to reorganize[/yellow]")
                return
            
            # 2. Parse diff into individual hunks
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Parsing changes into hunks...", total=None)
                hunks = parse_diff(full_diff, context_lines=self.config.hunks.context_lines)
                
                if not hunks:
                    self.console.print("[yellow]No hunks found to reorganize[/yellow]")
                    return
                
                self.console.print(f"[green]Found {len(hunks)} hunks to analyze[/green]")
                
                # Check if we have too many hunks for the AI to process
                if len(hunks) > self.config.hunks.max_hunks_per_prompt:
                    self.console.print(f"[yellow]Warning: {len(hunks)} hunks found, limiting to {self.config.hunks.max_hunks_per_prompt} for AI analysis[/yellow]")
                    hunks = hunks[:self.config.hunks.max_hunks_per_prompt]
                
                # 3. Send hunks to AI for commit organization
                progress.update(task, description="Analyzing changes with AI...")
                commit_plan = self.analyze_with_ai(hunks, full_diff)
            
            if not commit_plan:
                self.console.print("[red]Failed to generate commit plan[/red]")
                return
            
            # 3. Display the plan
            self.display_commit_plan(commit_plan)
            
            # 4. Execute or dry run
            if args.dry_run:
                self.console.print("\n[green]Dry run complete. Use without --dry-run to apply changes.[/green]")
            else:
                # Auto-accept if --yes flag is provided, otherwise ask for confirmation
                if args.yes or self.get_user_confirmation():
                    if args.yes:
                        self.console.print("\n[green]Auto-accepting commit plan (--yes flag provided)[/green]")
                    self.apply_commit_plan(commit_plan, hunks, full_diff, args.base)
                else:
                    self.console.print("Operation cancelled.")
                    
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    def get_full_diff(self, base_branch: str) -> Optional[str]:
        """Get the full diff between base branch and current branch."""
        try:
            # First check if we're in a git repo and the base branch exists
            subprocess.run(['git', 'rev-parse', '--git-dir'], 
                         check=True, capture_output=True)
            
            # Try to get the diff
            result = subprocess.run(
                ['git', 'diff', f'{base_branch}...HEAD'],
                capture_output=True, text=True, check=True
            )
            
            if not result.stdout.strip():
                return None
                
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            if 'unknown revision' in e.stderr:
                # Try with origin/main or other common base branches
                for alt_base in [f'origin/{base_branch}', 'develop', 'origin/develop']:
                    try:
                        result = subprocess.run(
                            ['git', 'diff', f'{alt_base}...HEAD'],
                            capture_output=True, text=True, check=True
                        )
                        if result.stdout.strip():
                            self.console.print(f"[yellow]Using {alt_base} as base branch[/yellow]")
                            return result.stdout
                    except subprocess.CalledProcessError:
                        continue
            raise Exception(f"Could not get diff from {base_branch}: {e.stderr}")
    
    def analyze_with_ai(self, hunks: List[Hunk], full_diff: str) -> Optional[List[Dict[str, Any]]]:
        """Send hunks to AI and get back commit organization plan."""
        try:
            # Ensure config is loaded
            if self.config is None:
                self.config = self.config_manager.load_config()
            
            ai_provider = UnifiedAIProvider(self.config)
            
            # Build hunk-based prompt
            prompt = self._build_hunk_prompt(hunks)
            
            response = ai_provider.generate(prompt)
            
            # With structured output, response should always be valid JSON
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            self.console.print(f"[red]AI returned invalid JSON: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]AI analysis failed: {e}[/red]")
            return None
    
    def _build_hunk_prompt(self, hunks: List[Hunk]) -> str:
        """Build a prompt that shows individual hunks with context for AI analysis."""
        
        prompt_parts = [
            "Analyze these code changes and organize them into logical commits for pull request review.",
            "",
            "Each change is represented as a 'hunk' with a unique ID. Group related hunks together",
            "based on functionality, not just file location. A single commit can contain hunks from",
            "multiple files if they implement the same feature or fix.",
            "",
            "For each commit, provide:",
            "1. A conventional commit message (type: description)",
            "2. The specific hunk IDs that should be included (not file paths!)",
            "3. A brief rationale for why these changes belong together",
            "",
            "Return your response in this exact structure:",
            "{",
            '  "commits": [',
            "    {",
            '      "message": "feat: add user authentication system",',
            '      "hunk_ids": ["auth.py:45-89", "models.py:23-45", "auth.py:120-145"],',
            '      "rationale": "Groups authentication functionality together"',
            "    }",
            "  ]",
            "}",
            "",
            "IMPORTANT: Use hunk_ids (not files) and group by logical functionality.",
            "",
            "CODE CHANGES TO ANALYZE:",
            ""
        ]
        
        # Add each hunk with its context
        for hunk in hunks:
            prompt_parts.extend([
                f"Hunk ID: {hunk.id}",
                f"File: {hunk.file_path}",
                f"Lines: {hunk.start_line}-{hunk.end_line}",
                "",
                "Context:",
                hunk.context if hunk.context else f"(Context unavailable for {hunk.file_path})",
                "",
                "Changes:",
                hunk.content,
                "",
                "---",
                ""
            ])
        
        return "\n".join(prompt_parts)
    
    
    def display_commit_plan(self, commit_plan: List[Dict[str, Any]]):
        """Display the proposed commit plan."""
        self.console.print("\n[bold]Proposed Commit Structure:[/bold]")
        
        for i, commit in enumerate(commit_plan, 1):
            panel_content = []
            panel_content.append(f"[bold]Message:[/bold] {commit['message']}")
            
            # Display hunk_ids grouped by file for readability
            if commit.get('hunk_ids'):
                hunk_ids = commit['hunk_ids']
                
                # Group hunks by file
                hunks_by_file = {}
                for hunk_id in hunk_ids:
                    if ':' in hunk_id:
                        file_path = hunk_id.split(':')[0]
                        if file_path not in hunks_by_file:
                            hunks_by_file[file_path] = []
                        hunks_by_file[file_path].append(hunk_id)
                    else:
                        # Fallback for malformed hunk IDs
                        if 'unknown' not in hunks_by_file:
                            hunks_by_file['unknown'] = []
                        hunks_by_file['unknown'].append(hunk_id)
                
                panel_content.append("[bold]Hunks:[/bold]")
                for file_path, file_hunks in hunks_by_file.items():
                    hunk_descriptions = []
                    for hunk_id in file_hunks:
                        if ':' in hunk_id:
                            line_range = hunk_id.split(':')[1]
                            hunk_descriptions.append(f"lines {line_range}")
                        else:
                            hunk_descriptions.append(hunk_id)
                    panel_content.append(f"  • {file_path}: {', '.join(hunk_descriptions)}")
            
            # Backward compatibility: also show files if present
            elif commit.get('files'):
                panel_content.append(f"[bold]Files:[/bold] {', '.join(commit['files'])}")
            
            panel_content.append(f"[bold]Rationale:[/bold] {commit['rationale']}")
            
            self.console.print(Panel(
                "\n".join(panel_content),
                title=f"Commit #{i}",
                border_style="blue"
            ))
    
    def get_user_confirmation(self) -> bool:
        """Get user confirmation to proceed."""
        self.console.print("\n[bold]Apply this commit structure?[/bold]")
        response = input("Continue? (y/N): ")
        return response.lower().strip() == 'y'
    
    def apply_commit_plan(self, commit_plan: List[Dict[str, Any]], hunks: List[Hunk], full_diff: str, base_branch: str):
        """Apply the commit plan using hunk-based staging."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                # 1. Create backup branch
                task = progress.add_task("Creating backup...", total=None)
                current_branch = subprocess.run(
                    ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                    capture_output=True, text=True, check=True
                ).stdout.strip()
                
                backup_branch = f"{current_branch}-backup-{int(__import__('time').time())}"
                subprocess.run(['git', 'branch', backup_branch], check=True)
                self.console.print(f"[green]Created backup branch: {backup_branch}[/green]")
                
                # 2. Create hunk ID to Hunk object mapping
                hunks_by_id = {hunk.id: hunk for hunk in hunks}
                
                # 3. Reset to base branch
                progress.update(task, description="Resetting to base branch...")
                # Use --hard reset to ensure working directory is clean
                # This is safe because we've already created a backup branch
                subprocess.run(['git', 'reset', '--hard', base_branch], check=True)
                
                # 4. Create new commits based on the plan
                progress.update(task, description="Creating new commits...")
                
                if commit_plan:
                    commits_created = 0
                    all_applied_hunk_ids = set()
                    
                    for i, commit in enumerate(commit_plan):
                        progress.update(task, description=f"Creating commit {i+1}/{len(commit_plan)}: {commit['message'][:50]}...")
                        
                        # Reset staging area before each commit
                        reset_staging_area()
                        
                        # Get hunk IDs for this commit
                        hunk_ids = commit.get('hunk_ids', [])
                        
                        # Backward compatibility: handle old format with files
                        if not hunk_ids and commit.get('files'):
                            # Convert files to hunk IDs by finding hunks that belong to those files
                            file_paths = commit.get('files', [])
                            hunk_ids = [hunk.id for hunk in hunks if hunk.file_path in file_paths]
                        
                        if hunk_ids:
                            try:
                                # Apply hunks using the hunk applicator
                                success = apply_hunks_with_fallback(hunk_ids, hunks_by_id, full_diff)
                                
                                if success:
                                    # Check if there are actually staged changes
                                    result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                                                          capture_output=True, text=True)
                                    
                                    if result.stdout.strip():
                                        # Create the commit
                                        subprocess.run([
                                            'git', 'commit', '-m', commit['message']
                                        ], check=True)
                                        commits_created += 1
                                        all_applied_hunk_ids.update(hunk_ids)
                                        self.console.print(f"[green]✓ Created commit: {commit['message']}[/green]")
                                        
                                        # Update working directory to match the commit
                                        # This ensures files reflect the committed state
                                        subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                                        
                                        # Additional sync to ensure working directory is fully updated
                                        # Force git to refresh the working directory state
                                        subprocess.run(['git', 'status'], capture_output=True, check=True)
                                    else:
                                        self.console.print(f"[yellow]Skipping commit '{commit['message']}' - no changes to stage[/yellow]")
                                else:
                                    self.console.print(f"[red]Failed to apply hunks for commit '{commit['message']}'[/red]")
                                    
                            except Exception as e:
                                self.console.print(f"[red]Error applying commit '{commit['message']}': {e}[/red]")
                        else:
                            self.console.print(f"[yellow]Skipping commit '{commit['message']}' - no hunks specified[/yellow]")
                    
                    # 5. Check for remaining hunks that weren't included in any commit
                    remaining_hunk_ids = [hunk.id for hunk in hunks if hunk.id not in all_applied_hunk_ids]
                    
                    if remaining_hunk_ids:
                        progress.update(task, description="Creating final commit for remaining changes...")
                        reset_staging_area()
                        
                        try:
                            success = apply_hunks_with_fallback(remaining_hunk_ids, hunks_by_id, full_diff)
                            if success:
                                result = subprocess.run(['git', 'diff', '--cached', '--name-only'], 
                                                      capture_output=True, text=True)
                                if result.stdout.strip():
                                    subprocess.run([
                                        'git', 'commit', '-m', 'chore: remaining uncommitted changes'
                                    ], check=True)
                                    commits_created += 1
                                    self.console.print(f"[green]✓ Created final commit for remaining changes[/green]")
                                    
                                    # Update working directory to match the commit
                                    subprocess.run(['git', 'reset', '--hard', 'HEAD'], check=True)
                                    
                                    # Additional sync to ensure working directory is fully updated
                                    # Force git to refresh the working directory state
                                    subprocess.run(['git', 'status'], capture_output=True, check=True)
                        except Exception as e:
                            self.console.print(f"[yellow]Could not apply remaining changes: {e}[/yellow]")
                    
                    # Working directory is now kept in sync after each commit,
                    # so no need for a final reset
                    
                    self.console.print(f"[green]Successfully created {commits_created} new commit(s)[/green]")
                    self.console.print(f"[blue]Backup available at: {backup_branch}[/blue]")
                
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Failed to apply commit plan: {e}[/red]")
            sys.exit(1)


def main():
    """Entry point for the git-smart-squash command."""
    cli = GitSmartSquashCLI()
    cli.main()


if __name__ == '__main__':
    main()