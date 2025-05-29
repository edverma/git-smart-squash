"""Zero-friction experience engine for git-smart-squash.

This module implements intelligent decision-making to minimize user friction.
"""

import os
import sys
import shutil
import subprocess
import argparse
from typing import Tuple, List, Dict, Optional
from pathlib import Path

from ..config.manager import ConfigManager
from ..core.models import Config, AIConfig
from ..core.git_parser import GitAnalyzer as GitCommitParser
from ..grouping.grouping_engine import GroupingEngine
from ..ai.message_generator import MessageGenerator
from ..git_operations.rebase_executor import RebaseScriptGenerator
from ..git_operations.safety_checks import GitSafetyChecker as SafetyChecker


class ZeroFrictionEngine:
    """Engine that provides intelligent defaults and automatic operation."""
    
    def __init__(self, logger=None):
        self.logger = logger or self._null_logger
        self.parser = GitCommitParser()
        self.config_manager = ConfigManager()
        
    def _null_logger(self, msg):
        """Null logger for when no logger is provided."""
        pass
        
    def detect_ai_provider(self) -> Tuple[str, Optional[str], Optional[str]]:
        """Auto-detect available AI provider in preference order.
        
        Returns:
            Tuple of (provider, model, base_url)
        """
        # Check for Ollama first (most user-friendly for local dev)
        if self._check_ollama():
            self.logger("🦙 Detected Ollama running locally")
            return "local", "devstral", "http://localhost:11434"
            
        # Check for API keys
        if os.environ.get("OPENAI_API_KEY"):
            self.logger("🔑 Found OpenAI API key")
            return "openai", "gpt-4o-mini", None
            
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.logger("🔑 Found Anthropic API key")
            return "anthropic", "claude-3-haiku-20240307", None
            
        # No AI provider found - require configuration
        raise RuntimeError(
            "❌ No AI provider configured. Git Smart Squash v2.x requires AI configuration.\n\n"
            "Please configure one of the following:\n"
            "  • OpenAI: Set OPENAI_API_KEY environment variable\n"
            "  • Anthropic: Set ANTHROPIC_API_KEY environment variable\n"
            "  • Local: Install and run Ollama (https://ollama.ai)\n\n"
            "For detailed configuration, see: example-config.yml"
        )
        
    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=1)
            return response.status_code == 200
        except:
            return False
            
    def get_smart_defaults(self) -> Config:
        """Generate intelligent configuration based on repository analysis."""
        config = self.config_manager.load_config()
        
        # Auto-detect AI provider
        provider, model, base_url = self.detect_ai_provider()
        config.ai.provider = provider
        if model:
            config.ai.model = model
        if base_url:
            config.ai.base_url = base_url
            
        # Analyze repository characteristics
        try:
            # Get recent commits to understand patterns
            commits = self.parser.get_commits_between("HEAD~20", "HEAD")
            
            # Adjust time window based on commit frequency
            if len(commits) > 15:
                config.grouping.time_window = 900  # 15 minutes for active repos
            elif len(commits) < 5:
                config.grouping.time_window = 3600  # 1 hour for slow repos
                
            # Check commit message quality
            conventional_count = sum(1 for c in commits if self._is_conventional(c.message))
            if conventional_count > len(commits) * 0.7:
                self.logger("📏 Detected conventional commit format in use")
                config.commit_format.scope_required = True
                
        except Exception:
            # Use defaults if analysis fails
            pass
            
        return config
        
    def _is_conventional(self, message: str) -> bool:
        """Check if commit message follows conventional format."""
        import re
        pattern = r'^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?: .+'
        return bool(re.match(pattern, message.lower()))
        
    def auto_fix_safety_issues(self) -> Tuple[bool, List[str]]:
        """Automatically fix common safety issues.
        
        Returns:
            Tuple of (success, actions_taken)
        """
        actions = []
        checker = SafetyChecker()
        
        # Check for uncommitted changes
        if checker._has_uncommitted_changes():
            self.logger("📦 Stashing uncommitted changes...")
            subprocess.run(["git", "stash", "push", "-m", "git-smart-squash auto-stash"], 
                         check=True, capture_output=True)
            actions.append("Stashed uncommitted changes")
            
        # Check if we're on main/master
        current = self.parser.get_current_branch()
        if current in ["main", "master"]:
            # Create a working branch
            branch_name = f"smart-squash-{os.getpid()}"
            self.logger(f"🌿 Creating working branch: {branch_name}")
            subprocess.run(["git", "checkout", "-b", branch_name], 
                         check=True, capture_output=True)
            actions.append(f"Created working branch: {branch_name}")
            
        return True, actions
        
    def calculate_confidence_score(self, groups, warnings) -> float:
        """Calculate confidence score for automatic execution.
        
        Returns:
            Score between 0.0 and 1.0
        """
        score = 1.0
        
        # Reduce confidence for warnings
        score -= len(warnings) * 0.1
        
        # Reduce confidence for too many groups
        if len(groups) > 10:
            score -= 0.2
        elif len(groups) > 5:
            score -= 0.1
            
        # Reduce confidence for single-commit groups
        single_groups = sum(1 for g in groups if len(g.commits) == 1)
        if single_groups > len(groups) * 0.5:
            score -= 0.2
            
        # Boost confidence for clean groupings
        multi_groups = len(groups) - single_groups
        if multi_groups > 3:
            score += 0.1
            
        return max(0.0, min(1.0, score))
        
    def should_auto_execute(self, groups, warnings) -> Tuple[bool, str]:
        """Determine if we should automatically execute without confirmation.
        
        Returns:
            Tuple of (should_execute, reason)
        """
        confidence = self.calculate_confidence_score(groups, warnings)
        
        if confidence >= 0.8:
            return True, f"High confidence ({confidence:.0%})"
        elif confidence >= 0.6:
            return False, f"Medium confidence ({confidence:.0%})"
        else:
            return False, f"Low confidence ({confidence:.0%})"
            
    def auto_recover_from_error(self, error: Exception) -> Tuple[bool, str]:
        """Attempt to automatically recover from common errors.
        
        Returns:
            Tuple of (recovered, action_taken)
        """
        error_msg = str(error).lower()
        
        # Handle merge conflicts
        if "conflict" in error_msg or "merge" in error_msg:
            self.logger("🔧 Attempting to resolve conflicts...")
            # Abort the rebase
            subprocess.run(["git", "rebase", "--abort"], capture_output=True)
            return True, "Aborted conflicting rebase, please resolve manually"
            
        # Handle stash issues
        if "stash" in error_msg:
            self.logger("📦 Recovering stashed changes...")
            subprocess.run(["git", "stash", "pop"], capture_output=True)
            return True, "Recovered stashed changes"
            
        # Handle missing commits
        if "unknown revision" in error_msg:
            return True, "Invalid base branch specified, using detected default"
            
        return False, ""


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
            msg_generator = MessageGenerator(config.ai)
            
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