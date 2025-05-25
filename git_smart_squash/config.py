"""Configuration management for Git Smart Squash."""

import os
import yaml
from typing import Optional, Dict, Any
from .models import Config, GroupingConfig, CommitFormatConfig, AIConfig, OutputConfig


class ConfigManager:
    """Manages configuration loading and validation."""
    
    DEFAULT_CONFIG_PATHS = [
        ".git-smart-squash.yml",
        ".git-smart-squash.yaml",
        "git-smart-squash.yml",
        "git-smart-squash.yaml"
    ]
    
    def __init__(self):
        self.config = Config()
    
    def load_config(self, config_path: Optional[str] = None) -> Config:
        """Load configuration from file or use defaults."""
        if config_path:
            if os.path.exists(config_path):
                return self._load_from_file(config_path)
            else:
                raise FileNotFoundError(f"Config file not found: {config_path}")
        
        # Try default locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if os.path.exists(path):
                return self._load_from_file(path)
        
        # Return default config if no file found
        return Config()
    
    def _load_from_file(self, config_path: str) -> Config:
        """Load configuration from a YAML file."""
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            config = Config()
            
            # Load grouping config
            if 'grouping' in data:
                grouping_data = data['grouping']
                config.grouping = GroupingConfig(
                    time_window=grouping_data.get('time_window', 1800),
                    min_file_overlap=grouping_data.get('min_file_overlap', 1),
                    similarity_threshold=grouping_data.get('similarity_threshold', 0.7)
                )
            
            # Load commit format config
            if 'commit_format' in data:
                format_data = data['commit_format']
                config.commit_format = CommitFormatConfig(
                    types=format_data.get('types', ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']),
                    scope_required=format_data.get('scope_required', False),
                    max_subject_length=format_data.get('max_subject_length', 50),
                    body_required=format_data.get('body_required', False)
                )
            
            # Load AI config
            if 'ai' in data:
                ai_data = data['ai']
                config.ai = AIConfig(
                    provider=ai_data.get('provider', 'openai'),
                    model=ai_data.get('model', 'gpt-4'),
                    api_key_env=ai_data.get('api_key_env', 'OPENAI_API_KEY')
                )
            
            # Load output config
            if 'output' in data:
                output_data = data['output']
                config.output = OutputConfig(
                    dry_run_default=output_data.get('dry_run_default', True),
                    backup_branch=output_data.get('backup_branch', True),
                    force_push_protection=output_data.get('force_push_protection', True)
                )
            
            return config
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {config_path}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading config file {config_path}: {e}")
    
    def save_config(self, config: Config, config_path: str):
        """Save configuration to a YAML file."""
        data = {
            'grouping': {
                'time_window': config.grouping.time_window,
                'min_file_overlap': config.grouping.min_file_overlap,
                'similarity_threshold': config.grouping.similarity_threshold
            },
            'commit_format': {
                'types': config.commit_format.types,
                'scope_required': config.commit_format.scope_required,
                'max_subject_length': config.commit_format.max_subject_length,
                'body_required': config.commit_format.body_required
            },
            'ai': {
                'provider': config.ai.provider,
                'model': config.ai.model,
                'api_key_env': config.ai.api_key_env
            },
            'output': {
                'dry_run_default': config.output.dry_run_default,
                'backup_branch': config.output.backup_branch,
                'force_push_protection': config.output.force_push_protection
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def create_default_config(self, config_path: str = ".git-smart-squash.yml"):
        """Create a default configuration file."""
        config = Config()
        self.save_config(config, config_path)
        return config_path
    
    def validate_config(self, config: Config) -> bool:
        """Validate configuration values."""
        errors = []
        
        # Validate grouping config
        if config.grouping.time_window <= 0:
            errors.append("grouping.time_window must be positive")
        
        if config.grouping.min_file_overlap < 0:
            errors.append("grouping.min_file_overlap must be non-negative")
        
        if not 0 <= config.grouping.similarity_threshold <= 1:
            errors.append("grouping.similarity_threshold must be between 0 and 1")
        
        # Validate commit format config
        if not config.commit_format.types:
            errors.append("commit_format.types cannot be empty")
        
        if config.commit_format.max_subject_length <= 0:
            errors.append("commit_format.max_subject_length must be positive")
        
        # Validate AI config
        valid_providers = ['openai', 'anthropic', 'local']
        if config.ai.provider not in valid_providers:
            errors.append(f"ai.provider must be one of: {', '.join(valid_providers)}")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        
        return True