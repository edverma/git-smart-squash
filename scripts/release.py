#!/usr/bin/env python3
"""
Git Smart Squash Release Helper

A Python script to automate common release tasks with better error handling
and cross-platform compatibility.
"""

import os
import sys
import subprocess
import argparse
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import hashlib
import urllib.request
import re

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class Logger:
    """Simple logger with colored output."""
    
    @staticmethod
    def info(msg: str):
        print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")
    
    @staticmethod
    def success(msg: str):
        print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")
    
    @staticmethod
    def warning(msg: str):
        print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {msg}")
    
    @staticmethod
    def error(msg: str):
        print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")

class ReleaseManager:
    """Manages the release process for git-smart-squash."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.package_name = "git-smart-squash"
        
    def run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        """Run a command and return the result."""
        if cwd is None:
            cwd = self.project_root
            
        Logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        
        if result.returncode != 0:
            Logger.error(f"Command failed: {' '.join(cmd)}")
            Logger.error(f"Error: {result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        
        return result
    
    def check_prerequisites(self) -> bool:
        """Check that required tools are available."""
        required_tools = ['git']
        
        # Check for Python (try multiple variants)
        python_found = False
        for python_cmd in ['python', 'python3', sys.executable]:
            if shutil.which(python_cmd):
                python_found = True
                break
        
        if not python_found:
            Logger.error("Python not found in PATH")
            return False
        
        # Check for pip (try multiple variants)
        pip_found = False
        for pip_cmd in ['pip', 'pip3']:
            if shutil.which(pip_cmd):
                pip_found = True
                break
        
        if not pip_found:
            Logger.error("Required tool 'pip' or 'pip3' not found in PATH")
            return False
        
        for tool in required_tools:
            if not shutil.which(tool):
                Logger.error(f"Required tool '{tool}' not found in PATH")
                return False
        
        return True
    
    def get_current_version(self) -> str:
        """Get the current version from the package."""
        try:
            # Try to import the package
            sys.path.insert(0, str(self.project_root))
            from git_smart_squash import __version__
            return __version__
        except ImportError:
            # Fallback: read from setup.py
            setup_py = self.project_root / "setup.py"
            if setup_py.exists():
                content = setup_py.read_text()
                match = re.search(r'version=[\"\']([^\"\']+)[\"\']', content)
                if match:
                    return match.group(1)
        
        raise ValueError("Could not determine current version")
    
    def validate_version(self, version: str) -> bool:
        """Validate semantic version format."""
        pattern = r'^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9]+)?$'
        return bool(re.match(pattern, version))
    
    def update_version_files(self, new_version: str):
        """Update version in all relevant files."""
        Logger.info(f"Updating version to {new_version}")
        
        files_to_update = [
            (self.project_root / "setup.py", r'version=[\"\'][^\"\']+[\"\']', f'version="{new_version}"'),
            (self.project_root / "git_smart_squash" / "__init__.py", 
             r'__version__ = [\"\'][^\"\']+[\"\']', f'__version__ = "{new_version}"'),
        ]
        
        # Update VERSION file
        version_file = self.project_root / "git_smart_squash" / "VERSION"
        version_file.write_text(new_version)
        
        for file_path, pattern, replacement in files_to_update:
            if file_path.exists():
                content = file_path.read_text()
                updated_content = re.sub(pattern, replacement, content)
                file_path.write_text(updated_content)
                Logger.info(f"Updated {file_path.name}")
    
    def run_tests(self):
        """Run the test suite."""
        Logger.info("Running tests...")
        # Try different Python commands
        python_cmd = sys.executable
        if not shutil.which(python_cmd):
            python_cmd = 'python3' if shutil.which('python3') else 'python'
        
        self.run_command([python_cmd, "-m", "pytest", "-xvs"])
        Logger.success("All tests passed")
    
    def build_package(self):
        """Build the Python package."""
        Logger.info("Building package...")
        
        # Clean previous builds
        for directory in ["dist", "build"]:
            dir_path = self.project_root / directory
            if dir_path.exists():
                shutil.rmtree(dir_path)
        
        # Find and remove egg-info directories
        for egg_info in self.project_root.glob("*.egg-info"):
            shutil.rmtree(egg_info)
        
        # Build package
        python_cmd = sys.executable
        if not shutil.which(python_cmd):
            python_cmd = 'python3' if shutil.which('python3') else 'python'
        
        self.run_command([python_cmd, "setup.py", "sdist", "bdist_wheel"])
        Logger.success("Package built successfully")
    
    def publish_to_pypi(self, test: bool = False):
        """Publish package to PyPI or TestPyPI."""
        if not shutil.which("twine"):
            Logger.error("twine not found. Install with: pip install twine")
            return
        
        if test:
            Logger.info("Publishing to TestPyPI...")
            self.run_command(["twine", "upload", "--repository", "testpypi", "dist/*"])
            Logger.success("Published to TestPyPI")
        else:
            Logger.info("Publishing to PyPI...")
            self.run_command(["twine", "upload", "dist/*"])
            Logger.success("Published to PyPI")
    
    def create_git_tag(self, version: str):
        """Create and push a git tag."""
        tag = f"v{version}"
        Logger.info(f"Creating git tag {tag}")
        
        self.run_command(["git", "add", "."])
        self.run_command(["git", "commit", "-m", f"chore: bump version to {version}"])
        self.run_command(["git", "tag", tag])
        self.run_command(["git", "push", "origin", "main"])
        self.run_command(["git", "push", "origin", tag])
        
        Logger.success(f"Git tag {tag} created and pushed")
    
    def get_pypi_package_info(self, package: str, version: str) -> Dict:
        """Get package information from PyPI."""
        url = f"https://pypi.org/pypi/{package}/{version}/json"
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read())
        except Exception as e:
            Logger.warning(f"Could not fetch PyPI info for {package}: {e}")
            return {}
    
    def calculate_sha256(self, url: str) -> str:
        """Calculate SHA256 hash of a file from URL."""
        Logger.info(f"Calculating SHA256 for {url}")
        
        with tempfile.NamedTemporaryFile() as tmp_file:
            with urllib.request.urlopen(url) as response:
                tmp_file.write(response.read())
                tmp_file.flush()
            
            hasher = hashlib.sha256()
            with open(tmp_file.name, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            
            return hasher.hexdigest()
    
    def generate_homebrew_formula(self, version: str):
        """Generate Homebrew formula."""
        Logger.info("Generating Homebrew formula...")
        
        formula_dir = self.project_root / "Formula"
        formula_dir.mkdir(exist_ok=True)
        
        # Calculate source archive SHA256
        archive_url = f"https://github.com/yourusername/{self.package_name}/archive/v{version}.tar.gz"
        try:
            source_sha256 = self.calculate_sha256(archive_url)
        except Exception as e:
            source_sha256 = "# TODO: Update with actual SHA256"
            Logger.warning(f"Could not calculate source SHA256: {e}. Please update manually.")
        
        # Get dependency information
        dependencies = {
            "pyyaml": "6.0.2",
            "rich": "14.0.0", 
            "openai": "1.44.0",
            "anthropic": "0.52.0",
            "requests": "2.31.0"
        }
        
        formula_content = f'''class GitSmartSquash < Formula
  include Language::Python::Virtualenv

  desc "Automatically reorganize messy git commit histories into clean, semantic commits"
  homepage "https://github.com/yourusername/{self.package_name}"
  url "{archive_url}"
  sha256 "{source_sha256}"
  license "MIT"

  depends_on "python@3.12"
'''
        
        # Add dependency resources
        for dep_name, dep_version in dependencies.items():
            try:
                pypi_info = self.get_pypi_package_info(dep_name, dep_version)
                if pypi_info and 'urls' in pypi_info:
                    # Find source distribution
                    source_dist = next((url for url in pypi_info['urls'] 
                                      if url['packagetype'] == 'sdist'), None)
                    if source_dist:
                        formula_content += f'''
  resource "{dep_name}" do
    url "{source_dist['url']}"
    sha256 "{source_dist['digests']['sha256']}"
  end
'''
            except Exception as e:
                Logger.warning(f"Could not get info for {dep_name}: {e}")
        
        formula_content += '''
  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: git-smart-squash", shell_output("#{bin}/git-smart-squash --help")
  end
end
'''
        
        formula_file = formula_dir / f"{self.package_name}.rb"
        formula_file.write_text(formula_content)
        
        Logger.success(f"Homebrew formula generated at {formula_file}")
    
    def generate_conda_recipe(self, version: str):
        """Generate conda-forge recipe."""
        Logger.info("Generating conda recipe...")
        
        recipe_dir = self.project_root / "conda-recipe"
        recipe_dir.mkdir(exist_ok=True)
        
        meta_yaml = f'''package:
  name: {self.package_name}
  version: {version}

source:
  url: https://pypi.io/packages/source/g/{self.package_name}/{self.package_name}-{{{{ version }}}}.tar.gz
  sha256: # TODO: Add SHA256 from PyPI

build:
  number: 0
  script: python -m pip install . -vv
  entry_points:
    - git-smart-squash = git_smart_squash.cli:main

requirements:
  host:
    - python >=3.8
    - pip
  run:
    - python >=3.8
    - pyyaml >=6.0
    - rich >=13.0.0
    - openai >=1.0.0
    - anthropic >=0.3.0
    - requests >=2.28.0

test:
  imports:
    - git_smart_squash
  commands:
    - git-smart-squash --help

about:
  home: https://github.com/yourusername/{self.package_name}
  license: MIT
  license_family: MIT
  license_file: LICENSE
  summary: Automatically reorganize messy git commit histories into clean, semantic commits
  description: |
    Git Smart Squash uses AI and heuristics to automatically group related commits
    and generate meaningful commit messages following conventional commit standards.

extra:
  recipe-maintainers:
    - yourusername
'''
        
        meta_file = recipe_dir / "meta.yaml"
        meta_file.write_text(meta_yaml)
        
        Logger.success(f"Conda recipe generated at {meta_file}")

def main():
    parser = argparse.ArgumentParser(description="Git Smart Squash Release Helper")
    parser.add_argument("version", help="New version number (e.g., 1.0.0)")
    parser.add_argument("--test", action="store_true", help="Use test repositories")
    parser.add_argument("--pypi-only", action="store_true", help="Only publish to PyPI")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Initialize release manager
    release_manager = ReleaseManager(project_root)
    
    # Validate version
    if not release_manager.validate_version(args.version):
        Logger.error(f"Invalid version format: {args.version}")
        Logger.error("Use semantic versioning (e.g., 1.0.0)")
        sys.exit(1)
    
    # Check prerequisites
    if not release_manager.check_prerequisites():
        Logger.error("Prerequisites check failed")
        sys.exit(1)
    
    # Get current version
    try:
        current_version = release_manager.get_current_version()
        Logger.info(f"Current version: {current_version}")
        Logger.info(f"New version: {args.version}")
    except ValueError as e:
        Logger.error(str(e))
        sys.exit(1)
    
    if args.dry_run:
        Logger.warning("DRY RUN MODE - No changes will be made")
        Logger.info("Would perform the following actions:")
        Logger.info("1. Update version files")
        if not args.skip_tests:
            Logger.info("2. Run tests")
        Logger.info("3. Build package")
        Logger.info("4. Publish to PyPI" + (" (test)" if args.test else ""))
        if not args.pypi_only and not args.test:
            Logger.info("5. Create git tag")
            Logger.info("6. Generate package manager files")
        return
    
    # Confirmation
    response = input(f"Release {args.version}? (y/N): ").strip().lower()
    if response != 'y':
        Logger.info("Release cancelled")
        return
    
    try:
        # Update version
        release_manager.update_version_files(args.version)
        
        # Run tests
        if not args.skip_tests:
            release_manager.run_tests()
        
        # Build package
        release_manager.build_package()
        
        # Publish to PyPI
        release_manager.publish_to_pypi(test=args.test)
        
        if args.test:
            Logger.success("Test release complete!")
            return
        
        # Create git tag
        release_manager.create_git_tag(args.version)
        
        if not args.pypi_only:
            # Generate package manager files
            release_manager.generate_homebrew_formula(args.version)
            release_manager.generate_conda_recipe(args.version)
        
        Logger.success("Release complete!")
        Logger.info("Next steps:")
        if not args.pypi_only:
            Logger.info("- Review generated Formula and conda recipe")
            Logger.info("- Submit to package managers as needed")
        Logger.info(f"- Package available: pip install {release_manager.package_name}")
        
    except Exception as e:
        Logger.error(f"Release failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()