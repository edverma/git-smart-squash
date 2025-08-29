# Git Smart Squash

Stop wasting time manually reorganizing commits. Let AI do it for you.

## The Problem

You've been there: 15 commits for a feature, half of them are "fix", "typo", or "WIP". Now you need to clean it up for PR review. Manually squashing and rewriting is tedious.

## The Solution

Git Smart Squash analyzes your changes and reorganizes them into logical commits with proper messages:

```bash
# Before: your messy branch
* fix tests
* typo  
* more auth changes
* WIP: working on auth
* update tests
* initial auth implementation

# After: clean, logical commits
* feat: implement JWT authentication system
* test: add auth endpoint coverage
```

## Quick Start

### 1. Install

```bash
# Using pip
pip install git-smart-squash

# Using pipx (recommended for isolated install)
pipx install git-smart-squash

# Using uv (fast Python package manager)
uv tool install git-smart-squash
```

### 2. Set up AI

**Option A: Local (Free, Private)**
```bash
# Install Ollama from https://ollama.com
ollama pull devstral  # Default model
```

**Option B: Cloud (Better results)**
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
```

**Option C: OpenRouter (100+ models)**
```bash
export OPENROUTER_API_KEY="sk-or-v1-your-key"
# Then run with: git-smart-squash --ai-provider openrouter
```

### 3. Run

```bash
cd your-repo
git-smart-squash
```

That's it. Review the plan and approve.

## Command Line Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--base` | Base branch to compare against | Config file or `main` |
| `--ai-provider` | AI provider to use (openai, anthropic, local, gemini, openrouter) | Configured in settings |
| `--model` | Specific AI model to use (see recommended models below) | Provider default |
| `--config` | Path to custom configuration file | `.git-smart-squash.yml` or `~/.git-smart-squash.yml` |
| `--auto-apply` | Apply commit plan without confirmation prompt | `false` |
| `--instructions`, `-i` | Custom instructions for AI (e.g., "Group by feature area") | None |
| `--no-attribution` | Disable attribution message in commits | `false` |
| `--debug` | Enable debug logging for detailed information | `false` |

## Recommended Models

### Default Models
- **OpenAI**: `gpt-4.1` (default)
- **Anthropic**: `claude-sonnet-4-20250514` (default)
- **Gemini**: `gemini-2.5-pro` (default)
- **OpenRouter**: `openai/gpt-5` (default)
- **Local/Ollama**: `devstral` (default)

### Model Selection
```bash
# Specify a different model
git-smart-squash --ai-provider openai --model gpt-4.1-mini

# For local Ollama
git-smart-squash --ai-provider local --model llama-3.1

# For OpenRouter (access to 100+ models)
git-smart-squash --ai-provider openrouter --model openai/gpt-5
git-smart-squash --ai-provider openrouter --model anthropic/claude-3.5-sonnet
```

## Custom Instructions

The `--instructions` parameter lets you control how commits are organized:

### Examples
```bash
# Add ticket prefixes
git-smart-squash -i "Prefix all commits with [ABC-1234]"

# Separate by type
git-smart-squash -i "Keep backend and frontend changes in separate commits"

# Limit commit count
git-smart-squash -i "Create at most 3 commits total"
```

### Tips for Better Results
- **Be specific**: "Group database migrations separately" works better than "organize nicely"
- **One instruction at a time**: Complex multi-part instructions may be partially ignored
- **Use better models**: Larger models follow instructions more reliably than smaller models

## Common Use Cases

### "I need to clean up before PR review"
```bash
git-smart-squash              # Shows plan and prompts for confirmation
git-smart-squash --auto-apply # Auto-applies without prompting
```

### "I work with a different main branch"
```bash
git-smart-squash --base develop
```

### "I want to use a specific AI provider"
```bash
git-smart-squash --ai-provider openai
git-smart-squash --ai-provider openrouter  # Access to 100+ models
```

## Safety

**Your code is safe:**
- Shows plan before making changes
- Creates automatic backup branch
- Requires clean working directory
- Never pushes without your command

**If something goes wrong:**
```bash
# Find backup
git branch | grep backup

# Restore
git reset --hard your-branch-backup-[timestamp]
```

## AI Providers

| Provider | Cost | Privacy |
|----------|------|---------|
| **Ollama** | Free | Local |
| **OpenAI** | ~$0.01 | Cloud |
| **Anthropic** | ~$0.01 | Cloud |
| **Gemini** | ~$0.01 | Cloud |
| **OpenRouter** | ~$0.005-$0.03 | Cloud |

## Advanced Configuration (Optional)

Want to customize? Create a config file:

**Project-specific** (`.git-smart-squash.yml` in your repo):
```yaml
ai:
  provider: openai  # Use OpenAI for this project
base: develop       # Use develop as the base branch for this project
```

**Global default** (`~/.git-smart-squash.yml`):
```yaml
ai:
  provider: local   # Always use local AI by default
base: main          # Default base branch for all projects
```

## Troubleshooting

### "Invalid JSON" Error
This usually means the AI model couldn't format the response properly:
- **With Ollama**: Switch from `llama2` to `mistral` or `mixtral`
- **Solution**: `ollama pull mistral` then retry
- **Alternative**: Use a cloud provider with `--ai-provider openai`

### Model Not Following Instructions
Some models struggle with complex instructions:
- **Use better models**: `--model gpt-4-turbo` or `--model claude-3-opus`
- **Simplify instructions**: One clear directive works better than multiple
- **Be explicit**: "Prefix with [ABC-123]" not "add ticket number"

### "Ollama not found" 
```bash
# Install from https://ollama.com
ollama serve
ollama pull devstral  # Default model
```

### Poor Commit Grouping
If the AI creates too many commits or doesn't group well:
- **Insufficient model**: Use a larger model
- **Add instructions**: `-i "Group related changes, max 3 commits"`
- **Provide Feedback**: Create an issue on GitHub and let us know what happened

### Installation Issues (Mac)
If you don't have pip or prefer isolated installs:
```bash
# Using pipx (recommended)
brew install pipx
pipx install git-smart-squash
```

### "No changes to reorganize"
```bash
git log --oneline main..HEAD  # Check you have commits
git diff main                 # Check you have changes
```

### Large Diffs / Token Limits
Local models have a ~32k token limit. For large changes:
- Use `--base` with a more recent commit
- Switch to cloud: `--ai-provider openai`
- Split into smaller PRs

### Need More Help?

Check out our [detailed documentation](DOCUMENTATION.md) or open an issue!

## License

MIT License - see [LICENSE](LICENSE) file for details.

