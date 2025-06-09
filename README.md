# Git Smart Squash

An AI-powered tool that intelligently reorganizes your git commits into logical, reviewable chunks perfect for pull requests.

## What It Does

Instead of manually squashing and organizing commits, Git Smart Squash:

1. **Analyzes your entire diff** between your feature branch and the main branch
2. **Uses AI to organize changes** into logical, reviewable commits
3. **Automatically restructures your git history** to match the AI's recommendations
4. **Creates clean, conventional commits** that are easy for reviewers to understand

### Before vs After

**Before** (messy commits):
```
* 3a1b2c3 WIP: auth stuff and models
* 4d5e6f7 more changes
* 8g9h0i1 tests and docs
```

**After** (AI-organized commits):
```
* a1b2c3d feat: implement user authentication system
* e4f5g6h test: add comprehensive auth test coverage  
* i7j8k9l docs: update API documentation for auth endpoints
```

## Installation

### Install from PyPI (Recommended)

```bash
pip install git-smart-squash
```

### Alternative Installation Methods

**Using pipx (isolated environment):**
```bash
pipx install git-smart-squash
```

**From source:**
```bash
git clone https://github.com/your-username/git-smart-squash.git
cd git-smart-squash
pip install -e .
```

## Quick Start

### 1. Set up AI Provider

**Local AI (Default - Recommended):**
```bash
# Install and start Ollama
ollama serve
ollama pull devstral
```

**Or use cloud AI:**
```bash
# For OpenAI
export OPENAI_API_KEY="your-api-key"

# For Anthropic  
export ANTHROPIC_API_KEY="your-api-key"

# For Google Gemini
export GEMINI_API_KEY="your-api-key"
```

### 2. Navigate to Your Git Repository

```bash
cd /path/to/your/repo
git checkout your-feature-branch
```

### 3. Run Git Smart Squash

**Dry run (see what it would do):**
```bash
git-smart-squash --dry-run
```

**Apply the changes:**
```bash
git-smart-squash
```

**Use short command:**
```bash
gss --dry-run  # Same as git-smart-squash --dry-run
```

## Usage Examples

### Basic Usage

```bash
# Preview the reorganization
git-smart-squash --dry-run

# Apply the reorganization  
git-smart-squash

# Use different base branch
git-smart-squash --base develop

# Use specific AI provider
git-smart-squash --ai-provider openai --model gpt-4.1
```

### Advanced Usage

```bash
# Use OpenAI (automatically uses gpt-4.1)
git-smart-squash --ai-provider openai

# Use Anthropic (automatically uses claude-sonnet-4-20250514)
git-smart-squash --ai-provider anthropic

# Use Google Gemini (automatically uses gemini-2.5-pro-preview-06-05)
git-smart-squash --ai-provider gemini

# Use specific model
git-smart-squash --ai-provider openai --model gpt-4.1

# Custom configuration
git-smart-squash --config .custom-config.yml
```

## AI Providers

### Local AI (Default)
- **Provider**: Ollama with devstral model
- **Cost**: Free
- **Privacy**: Completely local
- **Setup**: `ollama serve && ollama pull devstral`

### OpenAI
- **Provider**: OpenAI GPT models
- **Cost**: Pay per use
- **Setup**: Set `OPENAI_API_KEY` environment variable
- **Models**: gpt-4.1

### Anthropic
- **Provider**: Anthropic Claude models  
- **Cost**: Pay per use
- **Setup**: Set `ANTHROPIC_API_KEY` environment variable
- **Models**: claude-sonnet-4-20250514

### Google Gemini
- **Provider**: Google Gemini models
- **Cost**: Pay per use
- **Setup**: Set `GEMINI_API_KEY` environment variable
- **Models**: gemini-2.5-pro-preview-06-05

## Configuration

### Global Configuration

Create `~/.git-smart-squash.yml`:

```yaml
ai:
  provider: local  # or openai, anthropic, gemini
  model: devstral  # or gpt-4.1, claude-sonnet-4-20250514, gemini-2.5-pro-preview-06-05
  
output:
  backup_branch: true
```

### Project Configuration

Create `.git-smart-squash.yml` in your project root:

```yaml
ai:
  provider: openai
  model: gpt-4.1
```

## Safety Features

### Automatic Backups
- Creates backup branch: `your-branch-backup-1703123456`
- Preserves original work automatically
- Easy recovery if needed

### Recovery Commands
```bash
# If something goes wrong, recover your original branch:
git checkout your-branch-backup-1703123456
git checkout your-working-branch  
git reset --hard your-branch-backup-1703123456
```

### Validation
- Checks for clean working directory
- Validates base branch exists
- Confirms changes before applying

## How It Works

### The 4-Step Process

1. **Get Complete Diff**: Uses `git diff main...HEAD` to capture all changes
2. **AI Analysis**: Sends diff to AI with prompt for logical commit organization
3. **Display Plan**: Shows proposed commit structure for review
4. **Apply Changes**: Uses `git reset --soft` and creates new commits

### Technical Details

- **Single Python file** (~300 lines) for simplicity
- **Direct git commands** via subprocess
- **Rich terminal UI** for clear feedback
- **Conventional commit** message standards
- **JSON response parsing** with fallback mechanisms

## Token Management (Local AI)

For large repositories, the tool automatically:

- **Estimates token usage** (1 token ≈ 4 characters)
- **Sets optimal context size** with hard cap at 12,000 tokens
- **Adjusts prediction limits** up to 12,000 tokens
- **Scales timeouts** for large requests (up to 600 seconds)

## Troubleshooting

### Common Issues

**Ollama server not running:**
```bash
ollama serve
```

**Model not available:**
```bash
ollama pull devstral
```

**Large diffs timeout:**
- Break changes into smaller commits first
- Use `--base` with more recent branch
- Check token limit warnings

**API key issues:**
```bash
# Check environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
```

### Error Messages

**"No changes found to reorganize":**
- Check you're on the right branch
- Verify there are differences from base branch

**"Failed to generate commit plan":**
- Check AI provider configuration
- Verify network connectivity (for cloud providers)
- Try with smaller diff

## Examples

### Simple Authentication Feature

**Input diff:**
```diff
+++ b/src/auth.py
+def authenticate(user, password):
+    return user == "admin"

+++ b/tests/test_auth.py  
+def test_authenticate():
+    assert authenticate("admin", "pass")
```

**AI Output:**
```json
[
  {
    "message": "feat: add user authentication system",
    "files": ["src/auth.py", "tests/test_auth.py"], 
    "rationale": "Groups authentication implementation with its tests"
  }
]
```

### Complex Multi-File Feature

**AI organizes into logical commits:**
- `feat: implement user authentication core`
- `feat: add user model and database integration`  
- `test: add comprehensive auth test coverage`
- `docs: update API documentation for auth endpoints`

## Contributing

### Development Setup

```bash
git clone https://github.com/your-username/git-smart-squash.git
cd git-smart-squash
pip install -e .

# Run tests
python -m pytest test_functionality_comprehensive.py

# Run Ollama integration tests
./test_with_ollama.sh
```

### Running Tests

**Comprehensive functionality tests:**
```bash
python test_functionality_comprehensive.py
```

**Real Ollama integration tests:**
```bash
python test_ollama_integration.py
```

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: See `FUNCTIONALITY.md` for detailed technical specs
- **AI Integration**: See `OLLAMA_INTEGRATION.md` for token management details

---

**Made with ❤️ for developers who want cleaner git history**