"""Simplified command-line interface for Git Smart Squash."""

import argparse
import sys
import subprocess
import json
from typing import List, Dict, Any, Optional, Set
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .simple_config import ConfigManager
from .ai.providers.simple_unified import UnifiedAIProvider
from .diff_parser import parse_diff, Hunk
from .hunk_applicator import apply_hunks_with_fallback, reset_staging_area
from .logger import get_logger, LogLevel
from .dependency_validator import DependencyValidator, ValidationResult


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
                # Use custom instructions from CLI args, or fall back to config
                custom_instructions = args.instructions or self.config.ai.instructions
                commit_plan = self.analyze_with_ai(hunks, full_diff, custom_instructions)

            if not commit_plan:
                self.console.print("[red]Failed to generate commit plan[/red]")
                return

            # Validate the commit plan respects hunk dependencies
            validator = DependencyValidator()
            validation_result = validator.validate_commit_plan(
                commit_plan.get("commits", []),
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

            # 4. Ask for confirmation (unless auto-applying)
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

    def analyze_with_ai(self, hunks: List[Hunk], full_diff: str, custom_instructions: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Send hunks to AI and get back commit organization plan."""
        try:
            # Ensure config is loaded
            if self.config is None:
                self.config = self.config_manager.load_config()

            ai_provider = UnifiedAIProvider(self.config)

            # Build hunk-based prompt
            prompt = self._build_hunk_prompt(hunks, custom_instructions)

            response = ai_provider.generate(prompt)

            # With structured output, response should always be valid JSON
            result = json.loads(response)

            self.logger.debug(f"AI response type: {type(result).__name__}")
            self.logger.debug(f"AI response: {json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)}")

            # Validate the response structure
            if not isinstance(result, dict):
                self.console.print(f"[red]AI returned invalid response format: expected dict, got {type(result).__name__}[/red]")
                return None

            if "commits" not in result:
                self.console.print(f"[red]AI response missing 'commits' key[/red]")
                self.logger.debug(f"Available keys: {list(result.keys())}")
                return None

            return result

        except json.JSONDecodeError as e:
            self.console.print(f"[red]AI returned invalid JSON: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]AI analysis failed: {e}[/red]")
            return None

    def _build_hunk_prompt(self, hunks: List[Hunk], custom_instructions: Optional[str] = None) -> str:
        """Build a prompt that shows individual hunks with context for AI analysis."""

        prompt_parts = [
            "Analyze these code changes and organize them into logical commits for pull request review.",
            "",
            "Each change is represented as a 'hunk' with a unique ID. Group related hunks together",
            "based on functionality, not just file location. A single commit can contain hunks from",
            "multiple files if they implement the same feature or fix.",
            "",
        ]

        # Add custom instructions if provided
        if custom_instructions:
            prompt_parts.extend([
                "CUSTOM INSTRUCTIONS FROM USER:",
                custom_instructions,
                "",
            ])

        prompt_parts.extend([
            "For each commit, provide:",
            "1. A properly formatted git commit message following these rules:",
            "   - First line: max 80 characters (type: brief description)",
            "   - If more detail needed: empty line, then body with lines max 80 chars",
            "   - Use conventional commit format: feat:, fix:, docs:, test:, refactor:, etc.",
            "2. The specific hunk IDs that should be included (not file paths!)",
            "3. A brief rationale for why these changes belong together",
            "",
            "Return your response in this exact structure:",
            "{",
            '  "commits": [',
            "    {",
            '      "message": "feat: add user authentication system\\n\\nImplemented JWT-based authentication with refresh tokens.\\nAdded user model with secure password hashing.",',
            '      "hunk_ids": ["auth.py:45-89", "models.py:23-45", "auth.py:120-145"],',
            '      "rationale": "Groups authentication functionality together"',
            "    }",
            "  ]",
            "}",
            "",
            "IMPORTANT:",
            "- Use hunk_ids (not files) and group by logical functionality",
            "- First line of commit message MUST be ≤80 characters",
            "- Use \\n for line breaks in multi-line messages",
            "",
            "CODE CHANGES TO ANALYZE:",
            ""
        ])

        # Add each hunk with its context
        for hunk in hunks:
            hunk_info = [
                f"Hunk ID: {hunk.id}",
                f"File: {hunk.file_path}",
                f"Lines: {hunk.start_line}-{hunk.end_line}",
            ]

            # Add dependency information if present
            if hunk.dependencies:
                dep_list = ", ".join(sorted(hunk.dependencies))
                hunk_info.append(f"[DEPENDS ON: {dep_list}] - These hunks MUST be in the same commit or come before this one")

            hunk_info.extend([
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

            prompt_parts.extend(hunk_info)

        return "\n".join(prompt_parts)


    def display_commit_plan(self, commit_plan: Dict[str, Any]):
        """Display the proposed commit plan."""
        self.console.print("\n[bold]Proposed Commit Structure:[/bold]")

        commits = commit_plan.get("commits", [])
        for i, commit in enumerate(commits, 1):
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
        try:
            response = input("Continue? (y/N): ")
            self.logger.debug(f"User input received: '{response}'")
            result = response.lower().strip() == 'y'
            self.logger.debug(f"Confirmation result: {result}")
            return result
        except (EOFError, KeyboardInterrupt):
            self.logger.debug("Input interrupted or EOF received")
            return False

    def apply_commit_plan(self, commit_plan: Dict[str, Any], hunks: List[Hunk], full_diff: str, base_branch: str, no_attribution: bool = False):
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

                commits = commit_plan.get("commits", [])
                if commits:
                    commits_created = 0
                    all_applied_hunk_ids = set()

                    for i, commit in enumerate(commits):
                        progress.update(task, description=f"Creating commit {i+1}/{len(commits)}: {commit['message'][:50]}...")

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
                                self.logger.debug(f"Attempting to apply {len(hunk_ids)} hunks for commit: {commit['message']}")
                                self.logger.debug(f"Hunk IDs: {hunk_ids}")

                                success = apply_hunks_with_fallback(hunk_ids, hunks_by_id, full_diff)

                                self.logger.debug(f"Hunk application result: {'success' if success else 'failed'}")

                                if success:
                                    # Check if there are actually staged changes
                                    result = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                                                          capture_output=True, text=True)

                                    staged_files = result.stdout.strip()
                                    self.logger.debug(f"Staged files after hunk application: {staged_files if staged_files else 'NONE'}")

                                    if staged_files:
                                        # Add attribution to commit message if not disabled
                                        commit_message = commit['message']
                                        if not no_attribution and self.config.attribution.enabled:
                                            attribution = "\n\n----\nMade with git-smart-squash\nhttps://github.com/edverma/git-smart-squash"
                                            full_message = commit_message + attribution
                                        else:
                                            full_message = commit_message

                                        # Create the commit
                                        subprocess.run([
                                            'git', 'commit', '-m', full_message
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
                                        self.logger.warning(f"No changes staged after applying hunks for commit: {commit['message']}")
                                        self.logger.debug("This can happen when:")
                                        self.logger.debug("  - Hunks failed to apply due to conflicts")
                                        self.logger.debug("  - Hunks were already applied in a previous commit")
                                        self.logger.debug("  - The patch content was invalid or empty")
                                        self.logger.debug("Run with --debug to see detailed hunk application logs")
                                else:
                                    self.console.print(f"[red]Failed to apply hunks for commit '{commit['message']}'[/red]")
                                    self.logger.error(f"Hunk application failed for commit: {commit['message']}")
                                    self.logger.debug(f"Failed hunk IDs: {hunk_ids}")

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
                                    # Add attribution to commit message if not disabled
                                    if not no_attribution and self.config.attribution.enabled:
                                        attribution = "\n\n----\nMade with git-smart-squash\nhttps://github.com/edverma/git-smart-squash"
                                        full_message = 'chore: remaining uncommitted changes' + attribution
                                    else:
                                        full_message = 'chore: remaining uncommitted changes'

                                    subprocess.run([
                                        'git', 'commit', '-m', full_message
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
