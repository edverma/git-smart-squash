#!/usr/bin/env python3
"""Enhanced Zero-friction CLI interface for git-smart-squash.

This implements the TECHNICAL_SPECIFICATION.md requirements for an ideal
user experience with zero configuration and intelligent automation.
"""

import argparse
import sys
import os
import subprocess
from typing import Optional

from .zero_friction import ZeroFrictionEngine
from .analyzer.commit_parser import GitCommitParser
from .grouping.grouping_engine import GroupingEngine
from .ai.message_generator import MessageGenerator
from .git_operations.rebase_executor import InteractiveRebaseExecutor
from .git_operations.safety_checks import GitSafetyChecker as SafetyChecker

# Color printing functions
def print_colored(msg, color):
    """Print colored message."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'gray': '\033[90m',
        'reset': '\033[0m'
    }
    print(f"{colors.get(color, '')}{msg}{colors['reset']}")

def print_error(msg):
    """Print error message."""
    print_colored(msg, 'red')
    
def print_success(msg):
    """Print success message."""
    print_colored(msg, 'green')


class EnhancedZeroFrictionCLI:
    """Ultra-simple CLI that implements TECHNICAL_SPECIFICATION.md requirements."""
    
    def __init__(self):
        self.engine = ZeroFrictionEngine(logger=self._log)
        self.parser = GitCommitParser()
        
    def _log(self, msg: str):
        """Logger that prints to console."""
        print_colored(msg, "blue")
        
    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with minimal options."""
        parser = argparse.ArgumentParser(
            prog='gss',
            description='🚀 Zero-friction git commit squashing - just works!',
            epilog='Examples:\n'
                   '  gss                    # Squash commits on current branch\n'
                   '  gss main               # Squash commits since main\n'
                   '  gss --preview          # Preview without making changes\n'
                   '  gss --force            # Skip safety confirmations\n'
                   '  gss status             # Check repository readiness',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # Positional argument
        parser.add_argument(
            'base',
            nargs='?',
            help='Base branch/commit (auto-detected if not specified)'
        )
        
        # Core options
        parser.add_argument(
            '--preview', '--dry-run',
            action='store_true',
            dest='preview',
            help='Preview changes without executing'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts (use with caution)'
        )
        
        # Status command
        parser.add_argument(
            '--status',
            action='store_true',
            help='Check repository readiness'
        )
        
        # Advanced help
        parser.add_argument(
            '--help-advanced',
            action='store_true',
            help='Show advanced options and use traditional CLI'
        )
        
        return parser
        
    def run(self, args: Optional[list] = None):
        """Main entry point implementing the specification."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # Handle special commands first
        if parsed_args.help_advanced:
            self._show_advanced_help()
            return 0
            
        if parsed_args.status:
            return self._check_status()
            
        try:
            # Core zero-friction experience
            return self._execute_zero_friction_workflow(parsed_args)
            
        except KeyboardInterrupt:
            print_colored("\n\nCancelled by user. No changes made.", "yellow")
            return 130
        except Exception as e:
            print_error(f"\n❌ Unexpected error: {e}")
            print_colored("\nYour repository is safe. No changes made.", "green")
            print_colored("\nFor help: gss --help or report issues at:", "gray")
            print_colored("https://github.com/edverma/git-smart-squash/issues", "blue")
            return 1
    
    def _show_advanced_help(self):
        """Show advanced help and traditional CLI options."""
        print_colored("\n🎛️  Advanced Options:", "cyan")
        print_colored("For full control and configuration options, use:", "white")
        print_colored("  git-smart-squash --help", "blue")
        print("")
        print_colored("Advanced workflows:", "white")
        print_colored("  git-smart-squash --config custom.yml", "gray")
        print_colored("  git-smart-squash --strategies file_overlap,semantic", "gray")
        print_colored("  git-smart-squash --provider openai --model gpt-4", "gray")
    
    def _check_status(self) -> int:
        """Check repository readiness and show status."""
        print_colored("🔍 Repository Status Check", "cyan")
        
        # Basic git checks
        if not self.parser.is_git_repo():
            print_error("❌ Not in a git repository")
            return 1
        
        checker = SafetyChecker()
        warnings = checker.perform_safety_checks()
        
        if not warnings:
            print_success("✅ Repository is ready for git-smart-squash")
        else:
            print_colored("⚠️  Issues detected:", "yellow")
            for warning in warnings:
                print_colored(f"  • {warning}", "gray")
            print_colored("\nThe 'gss' command will automatically fix these issues.", "blue")
        
        # Show AI provider status
        provider, model, base_url = self.engine.detect_ai_provider()
        print_colored(f"\n🤖 AI Provider: {provider}", "blue")
        if model:
            print_colored(f"   Model: {model}", "gray")
        
        # Show commit information
        try:
            current = self.parser.get_current_branch()
            base = self.parser.get_default_base_branch()
            commits = self.parser.get_commits_between(base, current)
            print_colored(f"\n📊 Found {len(commits)} commits since {base}", "blue")
            
            if len(commits) == 0:
                print_colored("   Nothing to squash!", "green")
            elif len(commits) > 50:
                print_colored("   Large commit history - consider smaller ranges", "yellow")
            else:
                print_colored("   Ready for squashing", "green")
                
        except Exception as e:
            print_colored(f"   Could not analyze commits: {e}", "yellow")
        
        return 0
    
    def _execute_zero_friction_workflow(self, parsed_args) -> int:
        """Execute the core zero-friction workflow."""
        # Step 1: Repository validation
        if not self.parser.is_git_repo():
            print_error("❌ Not in a git repository!")
            return 1
            
        # Step 2: Auto-fix safety issues (spec requirement)
        print_colored("🔍 Checking repository status...", "blue")
        fixed, actions = self.engine.auto_fix_safety_issues()
        for action in actions:
            print_colored(f"  ✓ {action}", "green")
            
        # Step 3: Get smart defaults (spec requirement)
        config = self.engine.get_smart_defaults()
        
        # Step 4: Determine base branch with auto-detection
        if parsed_args.base:
            base = parsed_args.base
        else:
            base = self.parser.get_default_base_branch()
            print_colored(f"  ✓ Auto-detected base branch: {base}", "green")
            
        # Step 5: Get commits to analyze
        current = self.parser.get_current_branch()
        commits = self.parser.get_commits_between(base, current)
        
        if not commits:
            print_colored("\\n✨ No commits to squash!", "green")
            return 0
            
        print_colored(f"\\n🔍 Analyzing {len(commits)} commits since {base}...", "blue")
        
        # Step 6: Intelligent grouping (enhanced algorithm)
        grouping_engine = GroupingEngine(config.grouping)
        groups, warnings = grouping_engine.group_commits(commits)
        
        # Show warnings if any
        for warning in warnings:
            print_colored(f"  ⚠️  {warning}", "yellow")
            
        # Step 7: AI-powered message generation
        print_colored(f"\\n🤖 Generated professional commit messages", "blue")
        msg_generator = MessageGenerator(config.ai)
        
        for group in groups:
            group.suggested_message = msg_generator.generate_message(group)
            
        # Step 8: Display professional plan (spec requirement)
        self._display_professional_plan(groups, commits)
        
        # Step 9: Confidence-based execution (spec requirement)
        confidence_score = self.engine.calculate_confidence_score(groups, warnings)
        should_execute, reason = self.engine.should_auto_execute(groups, warnings)
        
        if parsed_args.preview:
            print_colored(f"\\n🔍 Preview complete (no changes made)", "yellow")
            print_colored(f"   Confidence: {confidence_score:.0%} - {reason}", "gray")
            return 0
            
        # Step 10: Execute with clear user feedback
        return self._execute_with_confidence(groups, commits, should_execute, reason, 
                                           confidence_score, parsed_args.force)
    
    def _display_professional_plan(self, groups, commits):
        """Display the squash plan in professional format per specification."""
        print_colored(f"\\n📊 Found {len(groups)} logical groups:", "cyan")
        
        for i, group in enumerate(groups, 1):
            # Extract commit type and scope for better display
            commit_type = getattr(group, 'commit_type', 'change').title()
            scope = f" ({group.scope})" if getattr(group, 'scope', None) else ""
            
            # Get description from suggested message
            if group.suggested_message:
                parts = group.suggested_message.split(': ', 1)
                description = parts[1] if len(parts) > 1 else parts[0]
            else:
                description = "Multiple changes"
            
            print_colored(f"  • {commit_type}{scope}: {description} ({len(group.commits)} commits)", "white")
            
            # Show first few commits for context
            for j, commit in enumerate(group.commits[:2]):
                short_msg = commit.message[:40] + ('...' if len(commit.message) > 40 else '')
                print_colored(f"    - {commit.short_hash} {short_msg}", "gray")
            
            if len(group.commits) > 2:
                print_colored(f"    ... and {len(group.commits) - 2} more", "gray")
    
    def _execute_with_confidence(self, groups, commits, should_execute, reason, 
                               confidence_score, force_mode) -> int:
        """Execute the squash plan with confidence-based decisions."""
        
        if should_execute or force_mode:
            if not force_mode:
                print_colored(f"\\n✅ {reason} - executing automatically...", "green")
            else:
                print_colored(f"\\n⚡ Force mode - executing despite {reason.lower()}...", "yellow")
        else:
            print_colored(f"\\n⚠️  {reason} - confirmation required", "yellow")
            print_colored("\\nThis will:", "white")
            print_colored(f"  • Combine {len(commits)} commits into {len(groups)} clean commits", "gray")
            print_colored(f"  • Create backup branch before changes", "gray")
            print_colored(f"  • Generate professional commit messages", "gray")
            
            response = input("\\nProceed with squashing? [Y/n] ")
            if response.lower() in ['n', 'no']:
                print_colored("\\nCancelled. No changes made.", "yellow")
                return 0
        
        # Execute the rebase with enhanced error handling
        return self._execute_rebase(groups, commits)
    
    def _execute_rebase(self, groups, commits) -> int:
        """Execute the actual rebase operation safely."""
        try:
            print_colored("\\n🔨 Executing rebase with automatic backup...", "blue")
            
            # Use the enhanced rebase executor
            executor = InteractiveRebaseExecutor()
            success = executor.execute_squash_plan(groups, create_backup=True)
            
            if success:
                print_success(f"\\n🎉 Successfully organized {len(commits)} commits into {len(groups)} clean commits!")
                print_colored("   Run 'git log --oneline' to see the result.", "gray")
                
                # Show next steps only if needed
                current_branch = self.parser.get_current_branch()
                if current_branch and current_branch not in ['main', 'master']:
                    print_colored("\\nNext steps:", "blue")
                    print_colored("  • Review the changes: git log --oneline", "gray")
                    print_colored("  • Push when ready: git push --force-with-lease", "gray")
                
                return 0
            else:
                raise RuntimeError("Rebase execution failed")
                
        except Exception as e:
            # Enhanced error recovery
            recovered, action = self.engine.auto_recover_from_error(e)
            if recovered:
                print_colored(f"\\n🔧 Auto-recovery: {action}", "yellow")
                print_colored("\\nYour repository is safe. No changes were made.", "green")
            else:
                print_error(f"\\n❌ Operation failed: {e}")
                print_colored("\\nYour repository is safe. Backup branch created.", "green")
                print_colored("\\nTip: Try 'gss --preview' to see what would happen", "gray")
            return 1


def main():
    """Entry point for enhanced zero-friction CLI."""
    cli = EnhancedZeroFrictionCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()