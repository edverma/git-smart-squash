"""Post-installation script to create default global configuration."""

import os
import sys
from .config import ConfigManager


def create_default_global_config():
    """Create a default global config file if none exists."""
    try:
        config_manager = ConfigManager()
        
        # Check if any global config already exists
        for path in config_manager.GLOBAL_CONFIG_PATHS:
            if os.path.exists(path):
                return  # Config already exists, don't overwrite
        
        # Create default global config
        config_path = config_manager.create_global_config()
        print(f"Created default global config at: {config_path}")
        
    except Exception as e:
        # Don't fail installation if config creation fails
        print(f"Warning: Could not create default config: {e}", file=sys.stderr)


def main():
    """Entry point for post-install script."""
    create_default_global_config()


if __name__ == "__main__":
    main()