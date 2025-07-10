# Git Smart Squash - Detailed Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Installation Guide](#installation-guide)
3. [Getting Started](#getting-started)
4. [Command Line Options](#command-line-options)
5. [AI Providers](#ai-providers)
6. [Configuration](#configuration)
7. [How It Works](#how-it-works)
8. [Advanced Usage](#advanced-usage)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)
11. [Technical Details](#technical-details)
12. [Contributing](#contributing)

## Introduction

Git Smart Squash is an AI-powered tool that transforms messy git commit histories into clean, logical commits perfect for pull request reviews. It analyzes your entire branch diff and uses AI to reorganize commits based on functionality, making your PRs easier to review and your git history more meaningful.

### Key Features

- **Intelligent Commit Organization**: AI analyzes your changes and groups them logically
- **Safe by Default**: Always shows plan before applying, creates automatic backups
- **Multiple AI Providers**: Supports local (Ollama) and cloud providers (OpenAI, Anthropic, Gemini)
- **Conventional Commits**: Generates standardized commit messages
- **Custom Instructions**: Guide the AI with specific organization rules

## Installation Guide

### Prerequisites

- Python 3.7 or higher
- Git installed and configured
- An AI provider (local or cloud)

### Installation Methods

#### 1. PyPI (Recommended)

```bash
pip install git-smart-squash
```

#### 2. Using pipx (Isolated Environment)

```bash
pipx install git-smart-squash
```

#### 3. Using uv (Fast Python Package Manager)

```bash
# Install with uv tool
uv tool install git-smart-squash

# Or in a project with uv pip
uv pip install git-smart-squash
```

#### 4. From Source

```bash
git clone https://github.com/your-username/git-smart-squash.git
cd git-smart-squash
pip install -e .
```

#### 5. Development Installation

```bash
git clone https://github.com/your-username/git-smart-squash.git
cd git-smart-squash
pip install -e ".[dev]"
```

### Verifying Installation

```bash
git-smart-squash --help
```

## Getting Started

### Step 1: Set Up Your AI Provider

#### Option A: Local AI with Ollama (Recommended for Privacy)

1. Install Ollama from https://ollama.com
2. Start the Ollama service:
   ```bash
   ollama serve
   ```
3. Pull the recommended model:
   ```bash
   ollama pull devstral
   ```

#### Option B: Cloud AI Providers

Set the appropriate environment variable:

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"

# Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# Google Gemini
export GEMINI_API_KEY="your-api-key"
```

### Step 2: Basic Usage

1. Navigate to your git repository:
   ```bash
   cd your-project
   ```

2. Check out your feature branch:
   ```bash
   git checkout feature-branch
   ```

3. Run Git Smart Squash:
   ```bash
   git-smart-squash
   ```

4. Review the proposed plan and confirm to apply it.

## Command Line Options

### Basic Syntax

```bash
git-smart-squash [OPTIONS]
```

### Available Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--base BASE` | | Base branch to compare against | Config file or `main` |
| `--ai-provider PROVIDER` | | AI provider to use (`local`, `openai`, `anthropic`, `gemini`) | Config file or `local` |
| `--model MODEL` | | Specific model to use | Provider default |
| `--config PATH` | | Path to configuration file | Auto-detected |
| `--auto-apply` | | Apply changes without confirmation prompt | Config file or `false` |
| `--instructions TEXT` | `-i` | Custom instructions for AI | Config file or none |
| `--no-attribution` | | Disable attribution message in commits | Config file or `false` |
| `--debug` | | Enable debug logging for detailed hunk application info | `false` |

### Examples

```bash
# Use a different base branch
git-smart-squash --base develop

# Use OpenAI with auto-apply
git-smart-squash --ai-provider openai --auto-apply

# Provide custom instructions
git-smart-squash -i "Group database changes separately from API changes"

# Use specific model
git-smart-squash --ai-provider anthropic --model claude-3-opus-20240229

# Use any custom model
git-smart-squash --ai-provider openai --model gpt-4-turbo-preview
git-smart-squash --ai-provider anthropic --model claude-3-haiku-20240307
git-smart-squash --ai-provider gemini --model gemini-1.5-flash
git-smart-squash --model llama3:70b  # For local Ollama

# Disable attribution message
git-smart-squash --no-attribution
```

## AI Providers

### Local AI (Ollama)

**Advantages:**
- Completely free
- 100% private - data never leaves your machine
- No API keys required
- Good performance for most use cases

**Limitations:**
- 32,000 token limit (approximately 128,000 characters)
- Requires local installation
- May be slower on older hardware

**Setup:**
```bash
ollama serve
ollama pull devstral
```

**Models:**
- `devstral` (default) - Optimized for code understanding
- `mistral` - Good alternative, avoids issues seen with llama2
- `mixtral` - General purpose with good code understanding  
- `codellama` - Code-focused model
- Any model available in Ollama - Specify with `--model` flag

**Note**: Avoid `llama2` as it tends to create too many separate commits instead of grouping related changes.

### OpenAI

**Advantages:**
- High-quality results
- Large context window (1M tokens / ~4M characters)
- Fast response times

**Setup:**
```bash
export OPENAI_API_KEY="sk-..."
```

**Models:**
- `gpt-4.1` (default) - Latest model with best quality
- `gpt-4o` - Previous generation, still very capable
- `gpt-4o-mini` - Faster and more economical
- `o1`, `o3` - Advanced reasoning models for complex reorganizations
- Any other OpenAI model - Specify with `--model` flag

**Pricing:** ~$0.01 per typical use

### Anthropic

**Advantages:**
- Excellent code understanding
- Large context window (200k tokens / ~800k characters)
- Strong reasoning capabilities

**Setup:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Models:**
- `claude-sonnet-4-20250514` (default) - Claude Sonnet 4, excellent for coding
- `claude-4-opus` - Top-tier model for complex code understanding
- `claude-3-5-sonnet-20241022` - Previous generation, still very good
- Any other Anthropic model - Specify with `--model` flag

**Pricing:** ~$0.01 per typical use

### Google Gemini

**Advantages:**
- Good code understanding
- Very large context window (1M tokens / ~4M characters)
- Competitive pricing
- Fast responses

**Setup:**
```bash
export GEMINI_API_KEY="..."
```

**Models:**
- `gemini-2.5-pro` (default) - Latest Gemini model with excellent performance
- `gemini-2.0-flash` - Faster and cost-effective for simpler tasks
- `gemini-2.0-pro` - Alternative with good multimodal capabilities
- Any other Gemini model - Specify with `--model` flag

**Pricing:** ~$0.01 per typical use

## Configuration

### Configuration Hierarchy

Git Smart Squash looks for configuration in this order:
1. Command line arguments (highest priority)
2. Project config: `.git-smart-squash.yml` in repository root
3. User config: `~/.git-smart-squash.yml`
4. System defaults (lowest priority)

### Configuration File Format

```yaml
# AI Provider Settings
ai:
  provider: local  # or openai, anthropic, gemini
  model: devstral  # optional, uses provider default if not set
                   # You can specify ANY model supported by the provider
  instructions: |  # Optional custom instructions for AI
    Always group database migrations separately.
    Keep test changes in their own commits.

# Base Branch Settings
base: main  # Default base branch for all operations

# Hunk Processing Settings
hunks:
  show_hunk_context: true  # Include context in hunk display
  context_lines: 3  # Number of context lines around changes
  max_hunks_per_prompt: 100  # Maximum hunks to send to AI at once

# Attribution Settings
attribution:
  enabled: true  # Set to false to disable "Made with git-smart-squash" message

# Auto-apply Settings
auto_apply: false  # Set to true to apply commits without confirmation
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GIT_SMART_SQUASH_CONFIG` | Override config file path |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `OLLAMA_HOST` | Ollama server URL (default: http://localhost:11434) |

## How It Works

### The Process

1. **Working Directory Validation**
   - Checks for uncommitted changes (staged, unstaged, untracked)
   - Provides helpful instructions if working directory is not clean
   - Ensures no data loss from uncommitted work

2. **Diff Extraction and Parsing**
   - Calculates complete diff: `git diff BASE...HEAD`
   - Parses diff into individual "hunks" (discrete change blocks)
   - Each hunk gets a unique ID based on file path and line numbers
   - Preserves context around changes for better understanding

3. **Hunk-Based AI Analysis**
   - Sends individual hunks to AI instead of raw diff
   - AI analyzes each hunk's purpose and relationships
   - Groups related hunks together based on functionality
   - Generates commit plan with hunk IDs (not just files)
   - Respects dependencies between hunks

4. **Plan Presentation**
   - Displays proposed commit structure
   - Shows which hunks (specific line ranges) belong to each commit
   - Groups hunks by file for readability
   - Provides rationale for each grouping
   - Waits for user confirmation (unless `--auto-apply`)

5. **Backup and Smart Application**
   - Creates persistent backup branch: `original-branch-backup-TIMESTAMP`
   - Final working directory check before applying changes
   - Hard resets to base branch: `git reset --hard BASE`
   - For each commit in the plan:
     - Resets staging area
     - Groups hunks by dependencies for proper ordering
     - Applies hunks using sophisticated strategies:
       - **Dependency-aware grouping**: Related hunks applied together
       - **Atomic application**: Try applying interdependent hunks as a single patch
       - **Sequential fallback**: Apply hunks one-by-one in dependency order
       - **Git native mechanisms**: Uses `git apply --index` for immediate sync
       - **Working directory integrity**: Saves/restores file states on failure
       - **Rollback on error**: Restores staging state if group fails
     - Creates commit with planned message
     - Forces working directory sync after each commit
   - If any error occurs, automatically restores from backup
   - Adds attribution to commits (unless disabled)

### Safety Mechanisms

Git Smart Squash is designed with multiple layers of safety:

#### 1. Working Directory Protection
- **Pre-operation validation**: Checks for uncommitted changes before starting
- **Clear error messages**: Provides specific instructions for handling different types of changes
- **Final validation**: Double-checks working directory is still clean before applying changes

#### 2. Automatic Backup System
- **Automatic backup creation**: Creates timestamped backup branch before any changes
- **Persistent backups**: Backup branches are preserved even after successful operations
- **Automatic restoration**: If any error occurs, automatically restores from backup
- **Easy manual recovery**: Clear instructions for manual restoration if needed

#### 3. Operation Safety
- **Diff validation**: Verifies changes exist before proceeding
- **Atomic operations**: All-or-nothing approach to prevent partial application
- **No automatic pushing**: Changes stay local until you explicitly push

## Advanced Usage

### Using Custom Models

Git Smart Squash supports ANY model offered by the configured AI provider. Simply use the `--model` flag:

```bash
# OpenAI examples
git-smart-squash --ai-provider openai --model gpt-3.5-turbo
git-smart-squash --ai-provider openai --model gpt-4-turbo-preview

# Anthropic examples
git-smart-squash --ai-provider anthropic --model claude-instant-1.2
git-smart-squash --ai-provider anthropic --model claude-3-haiku-20240307

# Gemini examples
git-smart-squash --ai-provider gemini --model gemini-1.5-flash
git-smart-squash --ai-provider gemini --model gemini-ultra

# Local Ollama examples
git-smart-squash --model codellama:13b
git-smart-squash --model mistral:latest
git-smart-squash --model llama2:70b
```

**Note**: When using custom models, the tool uses conservative token limits. If you know your model supports larger contexts, you can still use it, but be aware that very large diffs might be truncated.

### Custom Instructions

Guide the AI's commit organization with specific rules:

```bash
# Separate by architectural layer
git-smart-squash -i "Group by layer: database, API, frontend, tests"

# Follow team conventions
git-smart-squash -i "Follow our team's commit guidelines: feat/fix/chore prefixes, issue numbers"

# Complex organization
git-smart-squash -i "
1. Group all database schema changes together
2. Separate API endpoint additions from modifications
3. Keep test files with their implementation
4. Documentation updates in final commit
"
```

### Working with Large Diffs

For diffs exceeding token limits:

```bash
# Option 1: Use more recent base
git-smart-squash --base origin/main~10

# Option 2: Switch to cloud provider
git-smart-squash --ai-provider openai

# Option 3: Pre-organize manually
git rebase -i main  # Squash some commits first
git-smart-squash
```

### Integration with Git Workflows

#### Pre-PR Cleanup
```bash
# Before creating PR
git-smart-squash
git push --force-with-lease
```

#### Feature Branch Maintenance
```bash
# Periodically clean up long-running branches
git fetch origin
git-smart-squash --base origin/develop
```

#### CI/CD Integration
```yaml
# .github/workflows/pr-check.yml
- name: Check commit organization
  run: |
    git-smart-squash --base ${{ github.base_ref }}
```

### Handling Special Cases

#### Monorepo Organization
```bash
git-smart-squash -i "Group commits by package directory: packages/api, packages/web, packages/shared"
```

#### Preserving Specific Commits
```bash
git-smart-squash -i "Keep commits with 'BREAKING:' prefix separate"
```

#### Following Conventional Commits
```bash
git-smart-squash -i "Use conventional commit format: type(scope): description"
```

## Troubleshooting

### Common Issues and Solutions

#### "Working directory has uncommitted changes"

**Problem**: Git Smart Squash requires a clean working directory
**Solutions**:

For staged files:
```bash
# Option 1: Commit them
git commit -m "Your commit message"

# Option 2: Unstage them
git reset HEAD
```

For modified files:
```bash
# Option 1: Commit them
git add . && git commit -m "Your commit message"

# Option 2: Stash them temporarily
git stash
# Run git-smart-squash
git stash pop  # After completion
```

For untracked files:
```bash
# Option 1: Add and commit them
git add . && git commit -m "Add new files"

# Option 2: Add to .gitignore
echo "filename" >> .gitignore

# Option 3: Remove them (careful!)
rm filename
```

#### "Ollama server not running"

**Problem**: Can't connect to local AI
**Solution**:
```bash
# Start Ollama service
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

#### "Token limit exceeded" (Ollama)

**Problem**: Diff too large for local model (>30k tokens)
**Solutions**:
1. Use a cloud provider:
   ```bash
   git-smart-squash --ai-provider openai
   ```
2. Reduce diff size:
   ```bash
   git-smart-squash --base HEAD~20
   ```
3. Pre-squash some commits:
   ```bash
   git rebase -i HEAD~50
   ```

#### "No changes found to reorganize"

**Problem**: No diff between current branch and base
**Diagnosis**:
```bash
# Check current branch
git branch --show-current

# Verify diff exists
git diff main...HEAD --stat

# Check if already up to date
git log main..HEAD --oneline
```

#### "API key not found"

**Problem**: Cloud provider credentials missing
**Solution**:
```bash
# Set in current session
export OPENAI_API_KEY="your-key"

# Add to shell profile for persistence
echo 'export OPENAI_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

#### "Timeout during processing"

**Problem**: Large diff taking too long
**Solutions**:
1. Increase timeout in config:
   ```yaml
   ai:
     local:
       timeout: 1200  # 20 minutes
   ```
2. Use faster model:
   ```bash
   git-smart-squash --model gpt-4o-mini
   ```

#### "Operation failed - automatic restoration"

**Problem**: Something went wrong during commit reorganization
**What happens**: Git Smart Squash automatically restores from backup
**What you see**:
```
❌ Operation failed: [error message]
🔄 Repository automatically restored from backup: feature-branch-backup-1234567890
📦 Backup branch preserved for investigation: feature-branch-backup-1234567890
```

**Manual recovery** (if needed):
```bash
# Find all backup branches
git branch | grep backup

# Restore from specific backup
git reset --hard your-branch-backup-1234567890

# Delete backup when done (optional)
git branch -D your-branch-backup-1234567890
```

**Next steps**:
- Review the error message
- Check if working directory was clean
- Try with different options or custom instructions
- Report persistent issues on GitHub

### Debug Mode

Enable debug logging to see detailed information about hunk application and processing:

```bash
# Via command line flag
git-smart-squash --debug

# See what's happening during hunk application
git-smart-squash --debug --base develop
```

Debug mode shows:
- Detailed hunk application attempts
- Which hunks are being applied to each commit
- Fallback strategies when direct application fails
- Staging area operations
- Working directory synchronization steps

This is particularly useful when:
- Commits are being skipped unexpectedly
- You want to understand why certain changes aren't being applied
- Troubleshooting complex reorganizations

## Best Practices

### When to Use Git Smart Squash

✅ **Good Use Cases:**
- Before creating a pull request
- Cleaning up experimental development
- Reorganizing after multiple small fixes
- Converting "WIP" commits to meaningful history
- Standardizing commit messages

❌ **When to Avoid:**
- Shared branches (unless coordinated)
- After pushing to remote (requires force push)
- When commit timestamps are important
- For historical commits in main branch

### Commit Organization Strategies

1. **By Feature Area**
   ```bash
   git-smart-squash -i "Group by feature: auth, payments, notifications"
   ```

2. **By Change Type**
   ```bash
   git-smart-squash -i "Separate features, fixes, tests, and docs"
   ```

3. **By Risk Level**
   ```bash
   git-smart-squash -i "Group safe refactoring separately from behavior changes"
   ```

### Team Collaboration

1. **Document Conventions**
   Create team config:
   ```yaml
   # .git-smart-squash.yml
   instructions: |
     Follow our commit standards:
     - feat: New features
     - fix: Bug fixes
     - refactor: Code improvements
     - test: Test additions/changes
     - docs: Documentation only
   ```

2. **Coordinate Force Pushes**
   ```bash
   # Notify team before force pushing
   git-smart-squash
   git push --force-with-lease  # Safer than --force
   ```

3. **Review Generated Commits**
   Always review AI suggestions before applying

## Technical Details

### Architecture

Git Smart Squash is built with:
- **Core**: Python 3.7+ for cross-platform compatibility
- **Git Integration**: Direct subprocess calls to git commands
- **AI Communication**: HTTP clients for each provider
- **UI**: Rich terminal library for formatted output

### Hunk-Based Processing

Git Smart Squash uses a sophisticated hunk-based approach rather than file-based commits:

1. **Hunk Parsing**:
   - Extracts individual change blocks (hunks) from git diff
   - Each hunk has unique ID: `file_path:start_line-end_line`
   - Preserves context lines for better AI understanding
   - Detects dependencies between hunks

2. **Dependency Analysis**:
   - Identifies when hunks depend on each other
   - Groups interdependent hunks for atomic application
   - Uses topological sorting for correct application order
   - Prevents partial application of related changes

3. **Application Strategies**:
   - **Git Apply with --index**: Updates both staging and working directory
   - **State Preservation**: Saves file content before modifications
   - **Integrity Checks**: Verifies files aren't corrupted after patches
   - **Fallback Mechanisms**: Multiple strategies if primary fails
   - **Debug Logging**: Detailed logs available with `--debug` flag

### Performance Considerations

- **Token Estimation**: ~4 characters per token
- **Local AI**: 30k token limit, ~600s timeout
- **Cloud AI**: Provider-specific limits (usually 100k+)
- **Memory Usage**: Proportional to diff size
- **Hunk Limits**: Max 100 hunks per AI prompt (configurable)

### Security

- **Local AI**: No data leaves your machine
- **Cloud AI**: Diffs sent over HTTPS
- **No Credential Storage**: API keys from environment only
- **Backup Safety**: Original commits always preserved

## Contributing

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-username/git-smart-squash.git
cd git-smart-squash

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# All tests
python -m pytest

# With coverage
python -m pytest --cov=git_smart_squash

# Specific test file
python -m pytest tests/test_functionality.py
```

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public functions
- Run formatters:
  ```bash
  black git_smart_squash/
  isort git_smart_squash/
  ```

### Submitting Changes

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Make changes with tests
4. Run test suite
5. Submit pull request

### Adding AI Providers

To add a new AI provider:

1. Create provider class in `git_smart_squash/providers/`
2. Implement required methods:
   - `generate_commit_plan()`
   - `validate_credentials()`
3. Add to provider registry
4. Update documentation

---

For more information, visit the [GitHub repository](https://github.com/your-username/git-smart-squash) or open an issue for support.
