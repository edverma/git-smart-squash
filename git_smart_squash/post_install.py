"""Post-installation script to create default global configuration."""

import os
import sys
from .simple_config import ConfigManager


def create_default_global_config():
    """Create a default global config file if none exists."""
    try:
        config_manager = ConfigManager()
        
        # Check if global config already exists
        if os.path.exists(config_manager.default_config_path):
            return  # Config already exists, don't overwrite
        
        # Create default global config
        config_path = config_manager.create_default_config(global_config=True)
        print(f"Created default global config at: {config_path}")
        
    except Exception as e:
        # Don't fail installation if config creation fails
        print(f"Warning: Could not create default config: {e}", file=sys.stderr)


def main():
    """Entry point for post-install script."""
    create_default_global_config()


if __name__ == "__main__":
    main()