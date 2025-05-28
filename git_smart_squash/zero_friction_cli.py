#!/usr/bin/env python3
"""Zero-friction CLI interface for git-smart-squash.

This provides an ultra-simplified interface that requires zero configuration
and makes intelligent decisions automatically.
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
from .git_operations.rebase_executor import RebaseScriptGenerator
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


class ZeroFrictionCLI:
    """Ultra-simple CLI that just works."""
    
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
                   '  gss --dry-run          # Preview without making changes\n'
                   '  gss --help-advanced    # Show advanced options',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # Positional argument
        parser.add_argument(
            'base',
            nargs='?',
            help='Base branch/commit (auto-detected if not specified)'
        )
        
        # Minimal options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without executing'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts (use with caution)'
        )
        
        parser.add_argument(
            '--help-advanced',
            action='store_true',
            help='Show advanced options and use traditional CLI'
        )
        
        return parser
        
    def run(self, args: Optional[list] = None):
        """Main entry point."""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # Show advanced help
        if parsed_args.help_advanced:
            print_colored("\n🎛️  For advanced options, use: git-smart-squash --help", "yellow")
            return 0
            
        try:
            # Check if we're in a git repo
            if not self.parser.is_git_repo():
                print_error("Not in a git repository!")
                return 1
                
            # Auto-fix safety issues
            print_colored("\n🔍 Checking repository status...", "blue")
            fixed, actions = self.engine.auto_fix_safety_issues()
            for action in actions:
                print_colored(f"  ✓ {action}", "green")
                
            # Get smart defaults
            config = self.engine.get_smart_defaults()
            
            # Determine base branch
            if parsed_args.base:
                base = parsed_args.base
            else:
                base = self.parser.get_default_base_branch()
                print_colored(f"  ✓ Auto-detected base branch: {base}", "green")
                
            # Get commits
            current = self.parser.get_current_branch()
            commits = self.parser.get_commits_between(base, current)
            
            if not commits:
                print_colored("\n✨ No commits to squash!", "green")
                return 0
                
            print_colored(f"\n📊 Found {len(commits)} commits to analyze", "blue")
            
            # Group commits
            grouping_engine = GroupingEngine(config.grouping)
            groups, warnings = grouping_engine.group_commits(commits)
            
            # Show warnings
            for warning in warnings:
                print_colored(f"  ⚠️  {warning}", "yellow")
                
            # Generate messages
            print_colored(f"\n🤖 Generating commit messages...", "blue")
            msg_generator = MessageGenerator(config.ai, config.commit_format)
            
            for group in groups:
                group.suggested_message = msg_generator.generate_message(group)
                
            # Display plan
            print_colored(f"\n📋 Squash Plan ({len(groups)} groups):", "cyan")
            for i, group in enumerate(groups, 1):
                print_colored(f"\n  Group {i}: {len(group.commits)} commit(s)", "white")
                print_colored(f"  Message: {group.suggested_message.split(chr(10))[0]}", "green")
                for commit in group.commits:
                    print_colored(f"    - {commit.short_hash} {commit.message[:50]}", "gray")
                    
            # Check if we should auto-execute
            should_execute, reason = self.engine.should_auto_execute(groups, warnings)
            
            if parsed_args.dry_run:
                print_colored("\n🔍 Dry run complete (no changes made)", "yellow")
                return 0
                
            # Execute or confirm
            if should_execute or parsed_args.force:
                if not parsed_args.force:
                    print_colored(f"\n✅ {reason} - executing automatically...", "green")
            else:
                print_colored(f"\n⚡ {reason} - confirmation required", "yellow")
                response = input("\nProceed with squashing? [Y/n] ")
                if response.lower() in ['n', 'no']:
                    print_colored("Cancelled.", "yellow")
                    return 0
                    
            # Execute the rebase
            try:
                print_colored("\n🔨 Executing rebase...", "blue")
                # Generate and execute rebase script
                generator = RebaseScriptGenerator()
                script_path = f"/tmp/git-smart-squash-{os.getpid()}.sh"
                generator.generate_rebase_script(groups, script_path)
                
                # Make script executable and run it
                os.chmod(script_path, 0o755)
                result = subprocess.run([script_path], capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"Rebase failed: {result.stderr}")
                print_success("\n🎉 Successfully squashed commits!")
                
                # Show next steps
                print_colored("\nNext steps:", "blue")
                print_colored("  • Review the changes: git log --oneline", "gray")
                print_colored("  • Force push if needed: git push --force-with-lease", "gray")
                
            except Exception as e:
                # Try to auto-recover
                recovered, action = self.engine.auto_recover_from_error(e)
                if recovered:
                    print_colored(f"\n🔧 {action}", "yellow")
                else:
                    print_error(f"\n❌ Rebase failed: {e}")
                return 1
                
        except KeyboardInterrupt:
            print_colored("\n\nCancelled by user.", "yellow")
            return 130
        except Exception as e:
            print_error(f"\n❌ Error: {e}")
            return 1
            
        return 0


def main():
    """Entry point for zero-friction CLI."""
    cli = ZeroFrictionCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()