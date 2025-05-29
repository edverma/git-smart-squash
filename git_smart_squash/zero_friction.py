"""Zero-friction experience engine for git-smart-squash.

This module implements intelligent decision-making to minimize user friction.
"""

import os
import sys
import shutil
import subprocess
from typing import Tuple, List, Dict, Optional
from pathlib import Path

from .config import ConfigManager
from .models import Config, AIConfig
from .analyzer.commit_parser import GitCommitParser
from .grouping.grouping_engine import GroupingEngine
from .ai.message_generator import MessageGenerator
from .git_operations.rebase_executor import RebaseScriptGenerator
from .git_operations.safety_checks import GitSafetyChecker as SafetyChecker


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
            
        # Default to local Ollama with devstral model
        self.logger("🦙 Using default local AI (devstral via Ollama)")
        self.logger("💡 Tip: Install Ollama and run 'ollama pull devstral' for best experience")
        return "local", "devstral", "http://localhost:11434"
        
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