"""Setup script for Git Smart Squash."""

from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import subprocess
import sys

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read version from VERSION file
with open(os.path.join(this_directory, 'git_smart_squash', 'VERSION')) as f:
    version = f.read().strip()

# Define requirements directly
requirements = [
    "pyyaml>=6.0",
    "rich>=13.0.0", 
    "openai>=1.0.0",
    "anthropic>=0.3.0",
    "tiktoken>=0.5.0",
    "google-generativeai>=0.8.5",
]


class PostInstallCommand(install):
    """Custom post-installation command."""
    
    def run(self):
        install.run(self)
        # Run post-install script to create default global config
        try:
            subprocess.check_call([sys.executable, "-c", 
                "from git_smart_squash.post_install import main; main()"])
        except Exception as e:
            print(f"Warning: Post-install setup failed: {e}", file=sys.stderr)

setup(
    name="git-smart-squash",
    version=version,
    author="Evan Verma",
    author_email="edverma@icloud.com",
    description="Automatically reorganize messy git commit histories into clean, semantic commits",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/edverma/git-smart-squash",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'git_smart_squash': ['VERSION'],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Version Control :: Git",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "git-smart-squash=git_smart_squash.cli:main",
            "gss=git_smart_squash.cli:main",
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
    },
    keywords="git, commit, squash, rebase, conventional-commits, ai",
    project_urls={
        "Bug Reports": "https://github.com/edverma/git-smart-squash/issues",
        "Source": "https://github.com/edverma/git-smart-squash",
        "Documentation": "https://github.com/edverma/git-smart-squash#readme",
    },
)