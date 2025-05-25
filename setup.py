"""Setup script for Git Smart Squash."""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="git-smart-squash",
    version="0.1.0",
    author="Git Smart Squash Team",
    author_email="dev@example.com",
    description="Automatically reorganize messy git commit histories into clean, semantic commits",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/git-smart-squash",
    packages=find_packages(),
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
        "local": [
            "requests>=2.28.0",  # For llama.cpp server communication
        ],
    },
    entry_points={
        "console_scripts": [
            "git-smart-squash=git_smart_squash.cli:main",
        ],
    },
    keywords="git, commit, squash, rebase, conventional-commits, ai",
    project_urls={
        "Bug Reports": "https://github.com/example/git-smart-squash/issues",
        "Source": "https://github.com/example/git-smart-squash",
        "Documentation": "https://github.com/example/git-smart-squash#readme",
    },
)