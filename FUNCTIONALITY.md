# Git Smart Squash - Simplified Functionality

## Overview

Git Smart Squash is an AI-powered tool that reorganizes messy git commit histories into clean, logical commits that are easy for reviewers to understand in pull requests.

## Core Concept

Instead of manually squashing and organizing commits, this tool:

1. **Gets the complete diff** between your feature branch and the base branch (usually `main`)
2. **Sends the diff to AI** with instructions to organize it into logical, reviewable commits
3. **Shows you the proposed structure** with commit messages and rationale
4. **Resets your commit history** and creates new commits based on the AI's recommendations

## How It Works

### Step 1: Analyze Changes
```bash
git-smart-squash --dry-run
```

The tool extracts the full diff between your current branch and the base branch:
```bash
git diff main...HEAD
```

### Step 2: AI Analysis

The complete diff is sent to an AI model with this prompt:

> "Analyze this git diff and organize it into logical, reviewable commits that would be easy for a reviewer to understand in a pull request. For each commit, provide a conventional commit message, the specific files to include, and rationale for the grouping."

### Step 3: Review Proposed Structure

The AI responds with a structured plan like:

```
Commit #1: feat: add user authentication system
Files: src/auth.py, src/models/user.py, tests/test_auth.py
Rationale: Groups all authentication-related changes together

Commit #2: docs: update API documentation for auth endpoints
Files: docs/api.md, README.md
Rationale: Separates documentation updates from implementation

Commit #3: refactor: extract validation utilities
Files: src/utils/validation.py, src/auth.py
Rationale: Isolates reusable validation logic
```

### Step 4: Apply Changes

If you approve the plan, the tool:

1. Creates a backup branch (`your-branch-backup-123456`)
2. Resets your branch to the base branch (`git reset --soft main`)
3. Creates new commits following the AI's plan
4. Preserves all your changes while organizing them logically

## Benefits

### For Developers
- **No manual commit organization** - AI handles the complex analysis
- **Consistent commit messages** - Follows conventional commit standards
- **Safe operation** - Always creates backup branches
- **Fast workflow** - Single command to reorganize entire branch

### For Reviewers
- **Logical commit progression** - Each commit represents a complete, related change
- **Clear commit messages** - Easy to understand what each commit does
- **Focused reviews** - Can review each logical change separately
- **Better git history** - Clean, semantic commits that tell a story

## Usage Examples

### Basic Usage
```bash
# Analyze and reorganize commits (dry run)
git-smart-squash --dry-run

# Apply the reorganization
git-smart-squash
```

### With Different Base Branch
```bash
git-smart-squash --base develop
```

### Using Specific AI Provider
```bash
git-smart-squash --ai-provider openai --model gpt-4.1
git-smart-squash --ai-provider anthropic --model claude-sonnet-4-20250514
```

## AI Providers

The tool supports multiple AI providers:

- **Local AI** (default): Uses Ollama with devstral model
- **OpenAI**: GPT-4.1
- **Anthropic**: Claude models

Configure via environment variables:
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
```

## Safety Features

### Automatic Backups
Every operation creates a backup branch with timestamp:
```
your-feature-branch-backup-1703123456
```

### Soft Reset
Uses `git reset --soft` to preserve all changes while reorganizing commits.

### Validation
- Ensures clean working directory
- Validates base branch exists
- Checks for unstaged changes

## Configuration

Minimal configuration in `~/.git-smart-squash.yml`:

```yaml
ai:
  provider: local  # or openai, anthropic
  model: devstral  # or gpt-4.1, claude-sonnet-4-20250514
  
output:
  backup_branch: true
```

## Comparison with Traditional Approach

### Traditional Manual Squashing
```bash
git rebase -i main
# Manually mark commits to squash/reword
# Edit commit messages
# Resolve conflicts
# Hope you didn't mess up
```

### Git Smart Squash
```bash
git-smart-squash
# AI analyzes entire diff
# Proposes logical commit structure
# Applies changes safely with backup
```

## Use Cases

### Perfect For
- **Feature branches** with many small commits
- **Experimental work** that needs cleanup before PR
- **Refactoring sessions** with mixed changes
- **Bug fixes** that evolved into larger changes

### Not Ideal For
- **Single logical commits** that are already clean
- **Merge commits** (use for feature branches only)
- **Shared branches** (only use on your own feature branches)

## Technical Implementation

The tool is intentionally simple:

1. **Single Python file** (`cli.py`) with ~300 lines
2. **Direct git commands** via subprocess
3. **AI integration** through unified provider interface
4. **Rich terminal UI** for clear feedback

This simplicity makes it:
- Easy to understand and modify
- Reliable and predictable
- Fast to execute
- Simple to debug

## Recovery

If something goes wrong:

```bash
# Switch to backup branch
git checkout your-branch-backup-123456

# Copy it back to your working branch
git checkout your-working-branch
git reset --hard your-branch-backup-123456
```

## Future Enhancements

Potential improvements while maintaining simplicity:

- **File-level commit splitting** - AI recommends which files go in each commit
- **Interactive editing** - Modify AI suggestions before applying
- **Template customization** - Custom prompts for different project types
- **Conflict resolution** - Handle complex merge scenarios

The core philosophy remains: let AI do the complex analysis, keep the tool simple and reliable.