"""Simplified command-line interface for Git Smart Squash."""

import argparse
import sys
import subprocess
import json
import os
from typing import List, Dict, Any, Optional, Set
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .simple_config import ConfigManager
from .ai.providers.simple_unified import UnifiedAIProvider
from .diff_parser import parse_diff, Hunk
from .utils.git_diff import get_full_diff as util_get_full_diff
from .hunk_applicator import apply_hunks_with_fallback, reset_staging_area
from .logger import get_logger, LogLevel
from .dependency_validator import DependencyValidator, ValidationResult
from .strategies.backup_manager import BackupManager


class GitSmartSquashCLI:
    """Simplified CLI for git smart squash."""

    def __init__(self):
        self.console = Console()
        self.config_manager = ConfigManager()
        self.config = None
        self.logger = get_logger()
        self.logger.set_console(self.console)

    def main(self):
        """Main entry point for the CLI."""
        parser = self.create_parser()
        args = parser.parse_args()

        # Set debug logging if requested
        if args.debug:
            self.logger.set_level(LogLevel.DEBUG)
            self.logger.debug("Debug logging enabled")

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
            if args.reasoning is not None:
                self.config.ai.reasoning = args.reasoning or self.config.ai.reasoning

            # Gentle pre-check: OpenAI models must be GPT-5 family
            if self.config.ai.provider.lower() == 'openai' and not str(self.config.ai.model).startswith('gpt-5'):
                self.console.print("[yellow]OpenAI provider now uses GPT-5 models only.[/yellow]")
                self.console.print("Use --model gpt-5 (or gpt-5-mini/gpt-5-nano), or choose another provider via --ai-provider.")
                sys.exit(1)
            if getattr(args, 'max_predict_tokens', None) is not None:
                self.config.ai.max_predict_tokens = args.max_predict_tokens or self.config.ai.max_predict_tokens

            # Use base branch from config if not provided via CLI
            if args.base is None:
                args.base = self.config.base

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
            help='Base branch to compare against (default: from config or main)'
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
            '--auto-apply',
            action='store_true',
            help='Apply the commit plan immediately without confirmation'
        )


        parser.add_argument(
            '--instructions', '-i',
            type=str,
            help='Custom instructions for AI to follow when organizing commits (e.g., "Group by feature area", "Separate tests from implementation")'
        )

        parser.add_argument(
            '--no-attribution',
            action='store_true',
            help='Disable the attribution message in commit messages'
        )

        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug logging for detailed hunk application information'
        )

        parser.add_argument(
            '--reasoning',
            choices=['high', 'medium', 'low', 'minimal'],
            default=None,
            help='Reasoning effort level for GPT-5 models (default: low)'
        )

        parser.add_argument(
            '--max-predict-tokens',
            type=int,
            default=None,
            help='Maximum tokens for completion/output (default: 200000)'
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

            # 1.5. Ensure working directory is clean before proceeding with analysis/application
            status_info = self._check_working_directory_clean()
            if not status_info['is_clean']:
                self._display_working_directory_help(status_info)
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
                # Use custom instructions from CLI args, or fall back to config
                custom_instructions = args.instructions or self.config.ai.instructions
                commit_plan = self.analyze_with_ai(hunks, full_diff, custom_instructions)

            if not commit_plan:
                self.console.print("[red]Failed to generate commit plan[/red]")
                return

            # Validate the commit plan respects hunk dependencies
            validator = DependencyValidator()
            # Normalize to list for validation
            commits_list = commit_plan if isinstance(commit_plan, list) else commit_plan.get("commits", [])
            validation_result = validator.validate_commit_plan(
                commits_list,
                hunks
            )

            if not validation_result.is_valid:
                # Show the dependencies as debug information only
                self.logger.debug("Dependency relationships detected between hunks (informational):")
                for error in validation_result.errors:
                    self.logger.debug(f"  • {error}")
                # Continue with the original plan - no need to reorganize

            # Log any warnings even if validation passed
            if validation_result.warnings:
                self.console.print("\n[yellow]Warnings:[/yellow]")
                for warning in validation_result.warnings:
                    self.console.print(f"  • {warning}")

            # 3. Display the plan
            self.display_commit_plan(commit_plan)

            # 4. Double-check working directory is clean before applying changes
            self.console.print("[dim]Final working directory check before applying changes...[/dim]")
            final_status_info = self._check_working_directory_clean()

            if not final_status_info['is_clean']:
                self.console.print("[red]❌ Working directory changed during operation![/red]")
                self._display_working_directory_help(final_status_info)
                return

            # 5. Ask for confirmation (unless auto-applying)
            # Auto-apply if --auto-apply flag is provided or if config says to auto-apply
            auto_apply_from_config = getattr(self.config, 'auto_apply', False)
            if args.auto_apply or auto_apply_from_config:
                if args.auto_apply:
                    self.console.print("\n[green]Applying commit plan (--auto-apply flag provided)[/green]")
                elif auto_apply_from_config:
                    self.console.print("\n[green]Auto-applying commit plan (configured in settings)[/green]")
                self.apply_commit_plan(commit_plan, hunks, full_diff, args.base, args.no_attribution)
            elif self.get_user_confirmation():
                self.apply_commit_plan(commit_plan, hunks, full_diff, args.base, args.no_attribution)
            else:
                self.console.print("Operation cancelled.")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    def get_full_diff(self, base_branch: str) -> Optional[str]:
        """Get the full diff between base branch and current branch."""
        return util_get_full_diff(base_branch, console=self.console)

    def analyze_with_ai(self, hunks: List[Hunk], full_diff: str, custom_instructions: Optional[str] = None):
        """Send hunks to AI and get back commit organization plan (as a list)."""
        try:
            # Ensure config is loaded
            if self.config is None:
                self.config = self.config_manager.load_config()

            ai_provider = UnifiedAIProvider(self.config)

            # Build hunk-based prompt
            prompt = self._build_hunk_prompt(hunks, custom_instructions)

            response = ai_provider.generate(prompt)

            # With structured output, response should be valid JSON
            result = json.loads(response)

            self.logger.debug(f"AI response type: {type(result).__name__}")
            self.logger.debug(f"AI response: {json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}")

            # Normalize to list of commits
            if isinstance(result, dict) and "commits" in result and isinstance(result["commits"], list):
                return result["commits"]
            if isinstance(result, list):
                return result
            self.console.print(f"[red]AI returned invalid response format: expected list or object with 'commits'[/red]")
            return None

        except json.JSONDecodeError as e:
            self.console.print(f"[red]AI returned invalid JSON: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]AI analysis failed: {e}[/red]")
            return None

    def _build_hunk_prompt(self, hunks: List[Hunk], custom_instructions: Optional[str] = None) -> str:
        from .utils.prompt_builder import build_hunk_prompt
        return build_hunk_prompt(hunks, custom_instructions)


    def display_commit_plan(self, commit_plan):
        from .utils.display import display_commit_plan as _display
        _display(self.console, commit_plan)

    def get_user_confirmation(self) -> bool:
        """Get user confirmation to proceed."""
        self.console.print("\n[bold]Apply this commit structure?[/bold]")
        try:
            response = input("Continue? (y/N): ")
            self.logger.debug(f"User input received: '{response}'")
            result = response.lower().strip() == 'y'
            self.logger.debug(f"Confirmation result: {result}")
            return result
        except (EOFError, KeyboardInterrupt):
            self.logger.debug("Input interrupted or EOF received")
            return False

    def apply_commit_plan(self, commit_plan, hunks: List[Hunk], full_diff: str, base_branch: str, no_attribution: bool = False):
        from .strategies.commit_applier import apply_commit_plan as _apply
        _apply(self, commit_plan, hunks, full_diff, base_branch, no_attribution)

    def _check_working_directory_clean(self) -> Dict[str, Any]:
        from .utils.working_dir import check_clean
        return check_clean()

    def _display_working_directory_help(self, status_info: Dict[str, Any]):
        from .utils.working_dir import display_help
        display_help(self.console, status_info)

        # (removed duplicate implementation; commit application lives in strategies.commit_applier)


def main():
    """Entry point for the git-smart-squash command."""
    cli = GitSmartSquashCLI()
    cli.main()


if __name__ == '__main__':
    main()
