#!/usr/bin/env python3
"""
Bump version number for git-smart-squash.
Usage: bump_version.py [major|minor|patch]
"""

import sys
import os
from pathlib import Path

def read_version():
    """Read current version from VERSION file."""
    version_file = Path(__file__).parent.parent / 'git_smart_squash' / 'VERSION'
    return version_file.read_text().strip()

def write_version(version):
    """Write new version to VERSION file."""
    version_file = Path(__file__).parent.parent / 'git_smart_squash' / 'VERSION'
    version_file.write_text(version)

def bump_version(current_version, bump_type='patch'):
    """Bump version based on type (major, minor, patch)."""
    parts = current_version.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {current_version}")
    
    major, minor, patch = map(int, parts)
    
    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return f"{major}.{minor}.{patch}"

def main():
    # Get bump type from command line or default to patch
    bump_type = sys.argv[1] if len(sys.argv) > 1 else 'patch'
    
    if bump_type not in ['major', 'minor', 'patch']:
        print(f"Error: Invalid bump type '{bump_type}'")
        print("Usage: bump_version.py [major|minor|patch]")
        sys.exit(1)
    
    # Read current version
    current_version = read_version()
    print(f"Current version: {current_version}")
    
    # Bump version
    new_version = bump_version(current_version, bump_type)
    print(f"New version: {new_version}")
    
    # Write new version
    write_version(new_version)
    print(f"Version updated to {new_version}")
    
    return new_version

if __name__ == '__main__':
    main()