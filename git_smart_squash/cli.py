"""Simplified command-line interface for Git Smart Squash."""

import argparse
import sys
import subprocess
import json
import os
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .simple_config import ConfigManager
from .ai.providers.simple_unified import UnifiedAIProvider


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
            
            # 2. Send diff to AI for commit organization
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Analyzing changes with AI...", total=None)
                commit_plan = self.analyze_with_ai(full_diff)
            
            if not commit_plan:
                self.console.print("[red]Failed to generate commit plan[/red]")
                return
            
            # 3. Display the plan
            self.display_commit_plan(commit_plan)
            
            # 4. Execute or dry run
            if args.dry_run:
                self.console.print("\n[green]Dry run complete. Use without --dry-run to apply changes.[/green]")
            else:
                if self.get_user_confirmation():
                    self.apply_commit_plan(commit_plan, args.base)
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
    
    def analyze_with_ai(self, diff: str) -> Optional[List[Dict[str, Any]]]:
        """Send diff to AI and get back commit organization plan."""
        try:
            # Ensure config is loaded
            if self.config is None:
                self.config = self.config_manager.load_config()
            
            ai_provider = UnifiedAIProvider(self.config)
            
            prompt = f"""Analyze this git diff and organize changes into logical commits for pull request review.

For each commit, provide:
1. A conventional commit message (type: description)
2. The specific file changes that should be included
3. A brief rationale for why these changes belong together

Return your response in the following structure:
{{
  "commits": [
    {{
      "message": "feat: add user authentication system",
      "files": ["src/auth.py", "src/models/user.py"],
      "rationale": "Groups authentication functionality together"
    }}
  ]
}}

If the diff is very large, provide best-effort organization with logical groupings.

DIFF TO ANALYZE:
{diff}"""
            
            response = ai_provider.generate(prompt)
            
            # With structured output, response should always be valid JSON
            return json.loads(response)
            
        except json.JSONDecodeError as e:
            self.console.print(f"[red]AI returned invalid JSON: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]AI analysis failed: {e}[/red]")
            return None
    
    
    def display_commit_plan(self, commit_plan: List[Dict[str, Any]]):
        """Display the proposed commit plan."""
        self.console.print("\n[bold]Proposed Commit Structure:[/bold]")
        
        for i, commit in enumerate(commit_plan, 1):
            panel_content = []
            panel_content.append(f"[bold]Message:[/bold] {commit['message']}")
            if commit.get('files'):
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
    
    def apply_commit_plan(self, commit_plan: List[Dict[str, Any]], base_branch: str):
        """Apply the commit plan by resetting and recreating commits."""
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
                
                # 2. Reset to base branch
                progress.update(task, description="Resetting to base branch...")
                subprocess.run(['git', 'reset', '--soft', base_branch], check=True)
                
                # 3. Create new commits based on the plan
                progress.update(task, description="Creating new commits...")
                
                if commit_plan:
                    # Unstage everything first
                    subprocess.run(['git', 'reset', 'HEAD'], check=True, capture_output=True)
                    
                    commits_created = 0
                    for i, commit in enumerate(commit_plan):
                        progress.update(task, description=f"Creating commit {i+1}/{len(commit_plan)}: {commit['message'][:50]}...")
                        
                        # Stage only the files for this commit
                        files_to_stage = commit.get('files', [])
                        if files_to_stage:
                            # Filter out files that don't exist (might have been deleted)
                            existing_files = []
                            for file_path in files_to_stage:
                                result = subprocess.run(['git', 'ls-files', '--error-unmatch', file_path], 
                                                      capture_output=True, text=True)
                                if result.returncode == 0:
                                    existing_files.append(file_path)
                                else:
                                    # Check if file exists but is untracked
                                    if os.path.exists(file_path):
                                        existing_files.append(file_path)
                            
                            if existing_files:
                                subprocess.run(['git', 'add'] + existing_files, check=True)
                                
                                # Create the commit
                                subprocess.run([
                                    'git', 'commit', '-m', commit['message']
                                ], check=True)
                                commits_created += 1
                            else:
                                self.console.print(f"[yellow]Skipping commit '{commit['message']}' - no files to stage[/yellow]")
                        else:
                            self.console.print(f"[yellow]Skipping commit '{commit['message']}' - no files specified[/yellow]")
                    
                    # Check if there are any remaining modified files that weren't included in commits
                    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        # There are still unstaged changes - stage and commit them
                        progress.update(task, description="Creating final commit for remaining changes...")
                        subprocess.run(['git', 'add', '.'], check=True)
                        subprocess.run([
                            'git', 'commit', '-m', 'chore: remaining uncommitted changes'
                        ], check=True)
                        commits_created += 1
                    
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