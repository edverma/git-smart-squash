# Git Smart Squash

Automatically reorganize messy git commit histories into clean, semantic commits suitable for pull request reviews.

## Overview

Git Smart Squash is a command-line tool that uses AI and heuristics to intelligently group related commits and generate meaningful commit messages following conventional commit standards. It helps developers clean up their commit history before creating pull requests.

## Features

- **Intelligent Commit Grouping**: Uses multiple strategies to group related commits:
  - File overlap analysis
  - Temporal proximity
  - Semantic similarity
  - Dependency chain detection

- **AI-Powered Message Generation**: Supports multiple AI providers:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic (Claude)
  - Local models (via Ollama or llama.cpp)

- **Interactive Review**: Preview and adjust groupings before applying changes

- **Safety First**: 
  - Dry-run mode by default
  - Automatic backup branch creation
  - Comprehensive safety checks

- **Configurable**: YAML configuration with sensible defaults

## Installation

### PyPI (pip)

```bash
pip install git-smart-squash
```

### Homebrew (macOS/Linux)

```bash
brew install edverma/tools/git-smart-squash
```

Both installation methods are fully supported and provide the same functionality.

### Requirements

- Python 3.8+
- Git 2.0+

### Development Installation

```bash
git clone https://github.com/example/git-smart-squash.git
cd git-smart-squash
pip install -e .
```

## Quick Start

```bash
# Basic usage - analyze commits between main and HEAD
git smart-squash

# Specify a different base branch
git smart-squash --base develop

# Dry run to see proposed changes
git smart-squash --dry-run

# Use local AI model instead of cloud APIs
git smart-squash --ai-provider local --model codellama

# Skip AI and use template-based messages
git smart-squash --no-ai
```

## Configuration

Git Smart Squash supports multiple configuration levels with the following precedence:

1. **Explicit config** (`--config path/to/config.yml`)
2. **Local repository config** (`.git-smart-squash.yml` in current directory)
3. **Global user config** (`~/.git-smart-squash.yml` or `~/.config/git-smart-squash/config.yml`)
4. **Default settings**

### Local Configuration

Create a `.git-smart-squash.yml` file in your repository for project-specific settings:

```bash
# Generate a local config file
git-smart-squash config --init
```

### Global Configuration

Create a global configuration that applies to all repositories:

```bash
# Generate a global config file
git-smart-squash config --init-global
```

This creates `~/.git-smart-squash.yml` with default settings that apply across all your repositories.

### Configuration Options

```yaml
grouping:
  time_window: 1800  # 30 minutes
  min_file_overlap: 1
  similarity_threshold: 0.7

commit_format:
  types: [feat, fix, docs, style, refactor, test, chore]
  scope_required: false
  max_subject_length: 50

ai:
  provider: openai  # or anthropic, local
  model: gpt-4
  api_key_env: OPENAI_API_KEY

output:
  dry_run_default: true
  backup_branch: true
  force_push_protection: true
```

## AI Provider Setup

### OpenAI
```bash
export OPENAI_API_KEY="your-api-key"
git smart-squash --ai-provider openai --model gpt-4
```

### Anthropic
```bash
export ANTHROPIC_API_KEY="your-api-key"
git smart-squash --ai-provider anthropic --model claude-3-sonnet-20240229
```

### Local Models (Ollama)
```bash
# Install and start Ollama
ollama serve
ollama pull codellama

# Use with git-smart-squash
git smart-squash --ai-provider local --model codellama
```

## Examples

### Basic Workflow

```bash
# 1. Check repository status
git smart-squash status

# 2. Analyze and group commits (dry run)
git smart-squash --dry-run

# 3. Review the generated script
cat git-smart-squash-script.sh

# 4. Apply changes if satisfied
git smart-squash --auto
```

### Advanced Usage

```bash
# Use specific grouping strategies
git smart-squash --strategies file_overlap temporal

# Custom time window for temporal grouping
git smart-squash --time-window 3600  # 1 hour

# Generate script without AI
git smart-squash --no-ai --dry-run --output my-rebase.sh
```

## How It Works

1. **Commit Analysis**: Extracts metadata, file changes, and diffs from git history
2. **Intelligent Grouping**: Applies multiple strategies to find related commits:
   - **File Overlap**: Groups commits that modify the same files
   - **Temporal**: Groups commits made within a time window
   - **Semantic**: Groups commits with similar messages or change patterns
   - **Dependency**: Groups commits that build upon each other
3. **Message Generation**: Uses AI or templates to create conventional commit messages
4. **Interactive Review**: Shows proposed groupings for user approval
5. **Safe Execution**: Creates backups and performs safety checks before applying changes

## Safety Features

- **Dry run by default**: Preview changes before applying
- **Automatic backups**: Creates backup branches before operations
- **Safety checks**: Verifies clean working directory, no merge conflicts, etc.
- **Rollback support**: Easy restoration from backup branches

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] Interactive TUI for grouping review and editing
- [ ] Integration with popular git GUIs
- [ ] Plugin system for custom grouping strategies
- [ ] Team-shared configuration profiles
- [ ] Integration with CI/CD pipelines
- [ ] Support for more AI providers

## Support

- [Documentation](https://github.com/example/git-smart-squash#readme)
- [Issue Tracker](https://github.com/example/git-smart-squash/issues)
- [Discussions](https://github.com/example/git-smart-squash/discussions)