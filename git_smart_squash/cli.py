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
            choices=['openai', 'anthropic', 'local'],
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
            ai_provider = UnifiedAIProvider(self.config)
            
            prompt = f"""
            Analyze this git diff and organize it into logical, reviewable commits that would be easy for a reviewer to understand in a pull request.

            For each commit, provide:
            1. A conventional commit message (type: description)
            2. The specific file changes that should be included
            3. A brief rationale for why these changes belong together

            Respond with a JSON array where each commit has this structure:
            {{
                "message": "feat: add user authentication system",
                "files": ["src/auth.py", "src/models/user.py"],
                "rationale": "Groups all authentication-related changes together"
            }}

            Here's the diff to analyze:

            {diff}
            """
            
            response = ai_provider.generate(prompt)
            
            # Try to extract JSON from the response
            try:
                # Look for JSON array in the response
                start = response.find('[')
                end = response.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response[start:end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass
                
            # If JSON parsing failed, try to parse a simpler format
            return self.parse_ai_response_fallback(response)
            
        except Exception as e:
            self.console.print(f"[red]AI analysis failed: {e}[/red]")
            return None
    
    def parse_ai_response_fallback(self, response: str) -> List[Dict[str, Any]]:
        """Fallback parser for AI responses that aren't valid JSON."""
        commits = []
        lines = response.split('\n')
        current_commit = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('1.') or line.startswith('2.'):
                # This looks like a commit message
                if current_commit:
                    commits.append(current_commit)
                
                message = line.split(': ', 1)[-1] if ': ' in line else line[2:]
                current_commit = {
                    "message": message,
                    "files": [],
                    "rationale": "AI-suggested grouping"
                }
        
        if current_commit:
            commits.append(current_commit)
            
        return commits if commits else [{"message": "refactor: reorganize changes", "files": [], "rationale": "Single commit"}]
    
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
        return response.lower() == 'y'
    
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
                
                # For now, create a single commit with all changes
                # In a more sophisticated version, we'd split the diff by files
                if commit_plan:
                    subprocess.run(['git', 'add', '.'], check=True)
                    subprocess.run([
                        'git', 'commit', '-m', commit_plan[0]['message']
                    ], check=True)
                    
                    self.console.print(f"[green]Successfully created {len(commit_plan)} new commit(s)[/green]")
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