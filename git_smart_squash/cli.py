"""Command-line interface for Git Smart Squash."""

import argparse
import sys
import os
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from .models import Config
from .config import ConfigManager
from .analyzer.commit_parser import GitCommitParser
from .grouping.grouping_engine import GroupingEngine
from .ai.message_generator import MessageGenerator, TemplateMessageGenerator
from .git_operations.safety_checks import GitSafetyChecker
from .git_operations.rebase_executor import RebaseScriptGenerator


class GitSmartSquashCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.console = Console()
        self.config_manager = ConfigManager()
        self.config: Optional[Config] = None
    
    def main(self):
        """Main entry point for the CLI."""
        parser = self.create_parser()
        args = parser.parse_args()
        
        try:
            # Load configuration
            self.config = self.config_manager.load_config(args.config)
            
            # Override config with command line arguments
            self._apply_cli_overrides(args)
            
            # Validate configuration
            self.config_manager.validate_config(self.config)
            
            # Execute the requested command
            if hasattr(args, 'func'):
                args.func(args)
            else:
                self.run_smart_squash(args)
                
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            prog='git-smart-squash',
            description='Automatically reorganize messy git commit histories into clean, semantic commits',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  git-smart-squash                             # Basic usage with defaults
  gss                                          # Same as above (short form)
  git-smart-squash --base develop             # Specify base branch
  gss --dry-run                               # Show proposed changes only
  git-smart-squash --auto                     # Skip interactive mode
  gss --ai-provider local                     # Use local AI model
  git-smart-squash --config custom.yml       # Use custom config file
            """
        )
        
        # Basic options
        parser.add_argument(
            '--base',
            default='main',
            help='Base branch to compare against (default: main)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show proposed changes without executing them'
        )
        
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Skip interactive mode and apply changes automatically'
        )
        
        parser.add_argument(
            '--config',
            help='Path to configuration file'
        )
        
        parser.add_argument(
            '--output',
            help='Output file for dry-run script'
        )
        
        # AI options
        parser.add_argument(
            '--ai-provider',
            choices=['openai', 'anthropic', 'local'],
            help='AI provider to use for message generation'
        )
        
        parser.add_argument(
            '--model',
            help='AI model to use (e.g., gpt-4, claude-3-sonnet-20240229)'
        )
        
        parser.add_argument(
            '--no-ai',
            action='store_true',
            help='Use template-based messages instead of AI'
        )
        
        # Grouping options
        parser.add_argument(
            '--time-window',
            type=int,
            help='Time window in seconds for temporal grouping'
        )
        
        parser.add_argument(
            '--strategies',
            nargs='+',
            choices=['file_overlap', 'temporal', 'semantic', 'dependency'],
            help='Grouping strategies to use'
        )
        
        # Utility commands
        subparsers = parser.add_subparsers(dest='command', help='Additional commands')
        
        # Config command
        config_parser = subparsers.add_parser('config', help='Configuration management')
        config_parser.add_argument('--init', action='store_true', help='Create default config file')
        config_parser.add_argument('--show', action='store_true', help='Show current configuration')
        config_parser.set_defaults(func=self.handle_config_command)
        
        # Status command
        status_parser = subparsers.add_parser('status', help='Show repository status')
        status_parser.set_defaults(func=self.handle_status_command)
        
        return parser
    
    def _apply_cli_overrides(self, args):
        """Apply command line argument overrides to config."""
        if args.ai_provider:
            self.config.ai.provider = args.ai_provider
        
        if args.model:
            self.config.ai.model = args.model
        
        if args.time_window:
            self.config.grouping.time_window = args.time_window
        
        if args.dry_run:
            self.config.output.dry_run_default = True
    
    def run_smart_squash(self, args):
        """Run the main smart squash operation."""
        # Perform safety checks
        safety_checker = GitSafetyChecker()
        if not self._perform_safety_checks(safety_checker, args.auto):
            return
            
        # Parse commits
        commits = self._parse_commits(args.base)
        if not commits:
            return
            
        # Group commits
        groups = self._group_commits(commits, args.strategies)
        if not groups:
            self.console.print("[yellow]No grouping opportunities found[/yellow]")
            return
            
        # Generate messages
        groups = self._generate_messages(groups, args.no_ai)
        
        # Display results
        self.display_grouping_results(groups, commits)
        
        # Show analysis
        grouping_engine = GroupingEngine(self.config.grouping)
        quality_analysis = grouping_engine.analyze_grouping_quality(groups)
        self.display_quality_analysis(quality_analysis)
        
        # Handle dry run or execution
        if args.dry_run or self.config.output.dry_run_default:
            self.handle_dry_run(groups, args.output)
        elif args.auto or self.get_user_confirmation():
            self.execute_squash(groups, safety_checker)
        else:
            self.console.print("Operation cancelled by user.")
    
    def display_grouping_results(self, groups, commits):
        """Display the grouping results in a formatted table."""
        self.console.print("\n[bold]Proposed Groupings:[/bold]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Group", width=8)
        table.add_column("Commits", width=8)
        table.add_column("Type", width=10)
        table.add_column("Files", width=15)
        table.add_column("Message", width=50)
        
        for i, group in enumerate(groups, 1):
            commit_count = str(len(group.commits))
            files_desc = f"{len(group.files_touched)} files"
            if len(group.files_touched) <= 2:
                files_desc = ", ".join(group.files_touched)
            
            # Color code by group size
            if len(group.commits) > 1:
                commit_count = f"[green]{commit_count}[/green]"
            else:
                commit_count = f"[dim]{commit_count}[/dim]"
            
            table.add_row(
                f"#{i}",
                commit_count,
                group.commit_type,
                files_desc,
                group.suggested_message[:47] + "..." if len(group.suggested_message) > 50 else group.suggested_message
            )
        
        self.console.print(table)
        
        # Show detailed view for multi-commit groups
        multi_commit_groups = [g for g in groups if len(g.commits) > 1]
        if multi_commit_groups:
            self.console.print("\n[bold]Detailed Grouping Information:[/bold]")
            for i, group in enumerate(multi_commit_groups, 1):
                panel_content = []
                panel_content.append(f"[bold]Rationale:[/bold] {group.rationale}")
                panel_content.append(f"[bold]Changes:[/bold] +{group.total_insertions} -{group.total_deletions}")
                panel_content.append(f"[bold]Original commits:[/bold]")
                
                for commit in group.commits:
                    panel_content.append(f"  • {commit.short_hash}: {commit.message}")
                
                self.console.print(Panel(
                    "\n".join(panel_content),
                    title=f"Group #{i}: {group.suggested_message}",
                    border_style="blue"
                ))
    
    def display_quality_analysis(self, analysis):
        """Display grouping quality analysis."""
        self.console.print(f"\n[bold]Grouping Analysis:[/bold]")
        self.console.print(f"  Quality Score: {analysis['quality_score']:.2f}/1.0")
        self.console.print(f"  Compression: {len(analysis['strategy_usage'])} groups from {analysis['total_commits']} commits")
        self.console.print(f"  Reduction: {analysis['compression_ratio']:.1%}")
        
        if analysis['strategy_usage']:
            strategies = ", ".join(f"{k}({v})" for k, v in analysis['strategy_usage'].items())
            self.console.print(f"  Strategies used: {strategies}")
    
    def get_user_confirmation(self) -> bool:
        """Get user confirmation to proceed."""
        self.console.print("\n[bold]Proceed with squashing?[/bold]")
        response = input("Apply these changes? (y/N): ")
        return response.lower() == 'y'
    
    def handle_dry_run(self, groups, output_path: Optional[str]):
        """Handle dry run mode."""
        if not output_path:
            output_path = "git-smart-squash-script.sh"
        
        script_generator = RebaseScriptGenerator()
        script_path = script_generator.generate_rebase_script(groups, output_path)
        
        self.console.print(f"\n[green]Dry-run script generated: {script_path}[/green]")
        self.console.print(f"Review the script and run it manually when ready:")
        self.console.print(f"  bash {script_path}")
    
    def execute_squash(self, groups, safety_checker: GitSafetyChecker):
        """Execute the actual squash operations."""
        # Create backup if configured
        if self.config.output.backup_branch:
            backup = safety_checker.create_backup_branch()
            self.console.print(f"[green]Created backup branch: {backup}[/green]")
        
        # For MVP, we generate scripts instead of direct execution
        self.console.print("[yellow]Direct execution will be implemented in future versions[/yellow]")
        self.console.print("For now, use --dry-run to generate a safe execution script")
    
    def handle_config_command(self, args):
        """Handle config subcommand."""
        if args.init:
            config_path = self.config_manager.create_default_config()
            self.console.print(f"[green]Created default configuration: {config_path}[/green]")
        
        elif args.show:
            if self.config:
                self.console.print("[bold]Current Configuration:[/bold]")
                # TODO: Pretty print configuration
                self.console.print(str(self.config))
            else:
                self.console.print("[yellow]No configuration loaded[/yellow]")
    
    def handle_status_command(self, args):
        """Handle status subcommand."""
        safety_checker = GitSafetyChecker()
        parser = GitCommitParser()
        
        if not safety_checker._is_git_repo():
            self.console.print("[red]Not in a git repository[/red]")
            return
        
        # Show git status
        warnings = safety_checker.perform_safety_checks()
        if warnings:
            self.console.print("[red]Issues detected:[/red]")
            for warning in warnings:
                self.console.print(f"  ❌ {warning}")
        else:
            self.console.print("[green]✅ Repository is ready for smart squash[/green]")
        
        # Show commit count
        try:
            base_branch = parser.get_default_base_branch()
            commits = parser.get_commits_between(base_branch)
            self.console.print(f"\n[blue]📊 {len(commits)} commits ahead of {base_branch}[/blue]")
        except Exception as e:
            self.console.print(f"[yellow]Could not analyze commits: {e}[/yellow]")
    
    def _perform_safety_checks(self, safety_checker: GitSafetyChecker, auto: bool) -> bool:
        """Perform safety checks and handle warnings."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Performing safety checks...", total=None)
            warnings = safety_checker.perform_safety_checks()
            
        if warnings:
            self.console.print("\n[yellow]Warnings detected:[/yellow]")
            for warning in warnings:
                self.console.print(f"  ⚠️  {warning}")
            
            if not auto:
                response = input("\nContinue anyway? (y/N): ")
                if response.lower() != 'y':
                    self.console.print("Operation cancelled.")
                    return False
        return True
    
    def _parse_commits(self, base_branch: str):
        """Parse commits between base branch and HEAD."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Parsing commits...", total=None)
            parser = GitCommitParser()
            
            try:
                # Try to detect default base branch if 'main' doesn't exist
                if base_branch == 'main':
                    base_branch = parser.get_default_base_branch()
                
                commits = parser.get_commits_between(base_branch)
                
                if not commits:
                    self.console.print(f"[yellow]No commits found between {base_branch} and HEAD[/yellow]")
                    return None
                
                self.console.print(f"Found {len(commits)} commits to analyze")
                return commits
                
            except Exception as e:
                self.console.print(f"[red]Failed to parse commits: {e}[/red]")
                return None
    
    def _group_commits(self, commits, strategies):
        """Group commits using specified strategies."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Grouping commits...", total=None)
            grouping_engine = GroupingEngine(self.config.grouping)
            strategies = strategies or ['file_overlap', 'temporal', 'semantic', 'dependency']
            return grouping_engine.group_commits(commits, strategies)
    
    def _generate_messages(self, groups, no_ai: bool):
        """Generate commit messages for groups."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            if no_ai:
                task = progress.add_task("Generating template messages...", total=None)
                message_generator = TemplateMessageGenerator()
                for group in groups:
                    group.suggested_message = message_generator.generate_message(group)
            else:
                try:
                    task = progress.add_task("Generating AI messages...", total=None)
                    message_generator = MessageGenerator(self.config.ai)
                    for group in groups:
                        if len(group.commits) > 1:  # Only generate for multi-commit groups
                            ai_message = message_generator.generate_message(group)
                            if ai_message:
                                group.suggested_message = ai_message
                except Exception as e:
                    self.console.print(f"[yellow]AI generation failed ({e}), using templates[/yellow]")
                    template_generator = TemplateMessageGenerator()
                    for group in groups:
                        group.suggested_message = template_generator.generate_message(group)
        return groups


def main():
    """Entry point for the git-smart-squash command."""
    cli = GitSmartSquashCLI()
    cli.main()


if __name__ == '__main__':
    main()