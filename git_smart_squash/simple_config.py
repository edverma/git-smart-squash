"""Simplified configuration for Git Smart Squash."""

import os
import yaml
from typing import Optional
from dataclasses import dataclass


@dataclass
class AIConfig:
    """AI provider configuration."""
    provider: str = "local"
    model: str = "devstral"
    api_key_env: Optional[str] = None
    instructions: Optional[str] = None


@dataclass
class HunkConfig:
    """Hunk-based grouping configuration."""
    show_hunk_context: bool = True
    context_lines: int = 3
    max_hunks_per_prompt: int = 100


@dataclass
class AttributionConfig:
    """Attribution message configuration."""
    enabled: bool = True


@dataclass
class Config:
    """Simplified configuration."""
    ai: AIConfig
    hunks: HunkConfig
    attribution: AttributionConfig
    auto_apply: bool = False


class ConfigManager:
    """Simplified configuration manager."""

    def __init__(self):
        self.default_config_path = os.path.expanduser("~/.git-smart-squash.yml")

    def _get_default_model(self, provider: str) -> str:
        """Get the default model for a given provider."""
        defaults = {
            'local': 'devstral',
            'openai': 'gpt-4.1',
            'anthropic': 'claude-sonnet-4-20250514',  # Claude Sonnet 4 model
            'gemini': 'gemini-2.5-pro'  # Gemini 2.5 Pro model
        }
        return defaults.get(provider, 'devstral')

    def load_config(self, config_path: Optional[str] = None) -> Config:
        """Load configuration from file or create default."""

        # Try to load from specified path, then default path
        paths_to_try = []
        if config_path:
            paths_to_try.append(config_path)

        # Try local project config
        if os.path.exists(".git-smart-squash.yml"):
            paths_to_try.append(".git-smart-squash.yml")

        # Try global config
        paths_to_try.append(self.default_config_path)

        config_data = {}
        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        config_data = yaml.safe_load(f) or {}
                    break
                except Exception:
                    continue

        # Create config with provider-aware defaults
        provider = config_data.get('ai', {}).get('provider', 'local')
        model = config_data.get('ai', {}).get('model')

        # If no model specified, use provider-specific default
        if not model:
            model = self._get_default_model(provider)

        ai_config = AIConfig(
            provider=provider,
            model=model,
            api_key_env=config_data.get('ai', {}).get('api_key_env'),
            instructions=config_data.get('ai', {}).get('instructions')
        )

        # Load hunk configuration
        hunk_config_data = config_data.get('hunks', {})
        hunk_config = HunkConfig(
            show_hunk_context=hunk_config_data.get('show_hunk_context', True),
            context_lines=hunk_config_data.get('context_lines', 3),
            max_hunks_per_prompt=hunk_config_data.get('max_hunks_per_prompt', 100)
        )

        # Load attribution configuration
        attribution_config_data = config_data.get('attribution', {})
        attribution_config = AttributionConfig(
            enabled=attribution_config_data.get('enabled', True)
        )

        # Load auto-apply setting
        auto_apply = config_data.get('auto_apply', False)

        return Config(ai=ai_config, hunks=hunk_config, attribution=attribution_config, auto_apply=auto_apply)

    def create_default_config(self, global_config: bool = False) -> str:
        """Create a default config file."""
        config = {
            'ai': {
                'provider': 'local',
                'model': 'devstral',
                'api_key_env': None
            },
            'hunks': {
                'show_hunk_context': True,
                'context_lines': 3,
                'max_hunks_per_prompt': 100
            },
            'attribution': {
                'enabled': True
            },
            'auto_apply': False
        }

        if global_config:
            path = self.default_config_path
        else:
            path = ".git-smart-squash.yml"

        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        return path
