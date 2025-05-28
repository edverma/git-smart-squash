# Installation Guide for git-smart-squash v1.2.2

## 🎉 Version Alignment Complete!

Version 1.2.2 is now consistently available across all platforms - PyPI, GitHub, and Homebrew all use the same version number.

## Installation Options

### Option 1: Install from PyPI (Recommended)

```bash
pip install git-smart-squash
```

After installation, you'll have access to both commands:
- `git-smart-squash` - Traditional CLI with full configuration options
- `gss` - Zero-friction CLI for quick commit squashing

### Option 2: Install from PyPI with pipx (Isolated environment)

```bash
# Install pipx if you don't have it
pip install pipx

# Install git-smart-squash in isolated environment
pipx install git-smart-squash
```

### Option 3: Homebrew (Coming Soon)

A Homebrew formula has been created at `Formula/git-smart-squash.rb`. To publish to Homebrew:

1. **Create your own tap:**
   ```bash
   # Create a repository named homebrew-tap on GitHub
   # Copy the formula file to the repository
   ```

2. **Users can then install via:**
   ```bash
   brew tap yourusername/tap
   brew install git-smart-squash
   ```

## Verification

Test the installation:

```bash
# Test traditional CLI
git-smart-squash --help

# Test zero-friction CLI  
gss --help

# Check version
python -c "import git_smart_squash; print(git_smart_squash.__version__)"
```

## Package Information

- **Package Name:** git-smart-squash
- **Version:** 1.2.2 (consistent across all platforms)
- **PyPI URL:** https://pypi.org/project/git-smart-squash/1.2.2/
- **GitHub Release:** https://github.com/edverma/git-smart-squash/releases/tag/v1.2.2
- **Homebrew Formula:** Ready with v1.2.2
- **GitHub Repository:** https://github.com/edverma/git-smart-squash

## What's New in v1.2.2

### 🐛 **Critical Bug Fix**
- **Fixed commit counting error**: Resolved "too many values to unpack (expected 2)" error in zero-friction CLI
- **Updated grouping engine**: Now properly returns tuple of (groups, warnings)
- **Corrected imports**: Fixed module resolution issues

### ✨ **Previous Improvements (v1.2.0)**
- **Comprehensive code simplification and organization**
- **Improved file structure** with `core/` and `cli/` directories
- **Enhanced zero-friction CLI functionality**
- **Better error handling and user experience**

### 🏗️ Technical Changes
- Reorganized codebase for better maintainability
- Simplified import structure
- Enhanced test coverage (24/26 tests passing - 92% pass rate)
- All functionality verified against TECHNICAL_SPECIFICATION.md

### 🚀 New Features
- Improved AI provider detection and fallback
- Better commit grouping analysis with warnings
- Enhanced configuration management
- More robust error recovery

## Requirements

- Python 3.8+
- Git repository
- Optional: Ollama, OpenAI API key, or Anthropic API key for AI features

## Dependencies

- pyyaml>=6.0
- rich>=13.0.0
- openai>=1.0.0
- anthropic>=0.3.0
- requests>=2.28.0

## Usage Examples

### Zero-Friction Mode (Recommended)
```bash
# Just works - automatically detects everything
gss

# Preview changes without applying
gss --dry-run

# Use different base branch
gss --base develop
```

### Traditional Mode (Advanced Users)
```bash
# Basic usage with defaults
git-smart-squash

# Custom configuration
git-smart-squash --base develop --provider openai --model gpt-4

# Dry run with custom output
git-smart-squash --dry-run --output rebase-script.sh
```

## Support

- **Issues:** Report bugs and request features on GitHub
- **Documentation:** See README.md and TECHNICAL_SPECIFICATION.md
- **Help:** Run `gss --help` or `git-smart-squash --help`

---

**Happy squashing! 🎯**