#!/usr/bin/env python3
"""
Simple script to publish git-smart-squash to PyPI.

Usage:
    python publish.py [VERSION]

If VERSION is not provided, it will use the current version from VERSION file.
If VERSION is provided, it will update the VERSION file and then publish.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and handle errors."""
    print(f"→ {description if description else ' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout.strip():
            print(f"  {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error: {e}")
        if e.stderr:
            print(f"  {e.stderr}")
        return False

def get_current_version():
    """Get current version from VERSION file."""
    version_file = Path("git_smart_squash/VERSION")
    if version_file.exists():
        return version_file.read_text().strip()
    return None

def update_version(new_version):
    """Update the VERSION file."""
    version_file = Path("git_smart_squash/VERSION")
    version_file.write_text(new_version)
    print(f"→ Updated version to {new_version}")

def clean_build_artifacts():
    """Clean up build artifacts."""
    print("🧹 Cleaning build artifacts...")
    
    # Remove build directories
    for dir_name in ["build", "dist", "*.egg-info"]:
        for path in Path(".").glob(dir_name):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  Removed {path}")
    
    # Remove __pycache__ directories
    for pycache in Path(".").rglob("__pycache__"):
        shutil.rmtree(pycache)

def build_package():
    """Build the package."""
    print("📦 Building package...")
    return run_command([sys.executable, "setup.py", "sdist", "bdist_wheel"], "Building distribution packages")

def upload_to_pypi():
    """Upload to PyPI using twine."""
    print("🚀 Uploading to PyPI...")
    
    # Check if twine is installed
    try:
        subprocess.run(["twine", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ twine not found. Installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "twine"], "Installing twine"):
            return False
    
    # Upload to PyPI
    return run_command(["twine", "upload", "dist/*"], "Uploading to PyPI")

def main():
    """Main function."""
    print("🔧 Git Smart Squash PyPI Publisher")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("setup.py").exists() or not Path("git_smart_squash").exists():
        print("❌ Error: Must be run from the git-smart-squash root directory")
        sys.exit(1)
    
    # Handle version argument
    if len(sys.argv) > 1:
        new_version = sys.argv[1]
        update_version(new_version)
    
    # Get current version
    version = get_current_version()
    if not version:
        print("❌ Error: Could not read version from git_smart_squash/VERSION")
        sys.exit(1)
    
    print(f"📋 Publishing version: {version}")
    
    # Clean build artifacts
    clean_build_artifacts()
    
    # Build package
    if not build_package():
        print("❌ Build failed")
        sys.exit(1)
    
    # Upload to PyPI
    if not upload_to_pypi():
        print("❌ Upload failed")
        sys.exit(1)
    
    print("✅ Successfully published to PyPI!")
    print(f"📦 Version {version} is now available")
    print(f"🔗 Install with: pip install --upgrade git-smart-squash")

if __name__ == "__main__":
    main()