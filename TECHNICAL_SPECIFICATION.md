# Git Smart Squash - Technical Specification

## 1. Overview

### 1.1 Purpose
Git Smart Squash is a command-line tool that automatically reorganizes messy git commit histories into clean, semantic commits suitable for pull request reviews. It provides both a traditional configuration-driven interface and a revolutionary zero-friction experience that works with minimal user intervention.

### 1.2 Problem Statement
Developers often create numerous small, work-in-progress commits while developing features. These commits are useful for backup but create noise during code reviews. Traditional solutions require:
- Complex configuration setup
- Manual intervention for safety issues
- Technical knowledge of git operations
- Multiple decision points and confirmations

### 1.3 Solution
A dual-interface automated tool that:
- **Traditional CLI**: Full-featured interface with extensive configuration options
- **Zero-Friction CLI**: Intelligent automation requiring zero setup and minimal decisions
- Analyzes commit relationships using multiple signals
- Groups related commits intelligently
- Generates conventional commit messages using AI or templates
- Provides confidence-based execution with automatic error recovery

## 2. User Interfaces

### 2.1 Zero-Friction Interface (`gss`)
**Philosophy**: Git commit squashing should be as simple as `git add .`

#### 2.1.1 Core Commands
```bash
# Primary usage - one command does everything
gss

# Utility commands
gss status                   # Check repository readiness
gss --preview               # Show changes without applying
gss --force                 # Apply even with low confidence
gss --base develop          # Use different base branch
gss --verbose               # Show detailed progress
```

#### 2.1.2 Zero Configuration Experience
- **Auto-detects AI providers**: Ollama → OpenAI → Anthropic → Templates
- **Intelligent defaults**: Repository-specific optimization
- **Proactive safety handling**: Automatic stashing, branch switching, file staging
- **Confidence-based execution**: Only asks when genuinely unsure

### 2.2 Traditional Interface (`git-smart-squash`)
**Philosophy**: Full control with extensive configuration options

#### 2.2.1 Core Commands
```bash
# Basic usage
git-smart-squash

# Configuration options
git-smart-squash --base develop --provider openai --model gpt-4
git-smart-squash --strategies file_overlap temporal semantic
git-smart-squash --config custom-config.yml
git-smart-squash --dry-run --output rebase-script.sh

# Utility commands
git-smart-squash config --init        # Create local config
git-smart-squash config --init-global # Create global config
git-smart-squash status              # Repository status
```

## 3. Functional Requirements

### 3.1 Core Features

#### 3.1.1 Commit Analysis
- **Input**: Range of commits (current branch vs base branch)
- **Processing**:
  - Extract commit metadata (hash, author, timestamp, message)
  - Retrieve file changes for each commit
  - Calculate diff statistics (insertions, deletions)
  - Store full diff content for AI analysis
- **Output**: Structured commit objects with all relevant data

#### 3.1.2 Intelligent Grouping (4 Strategies)
- **File Overlap**: Commits modifying the same files
- **Temporal Proximity**: Commits within configurable time window (default: 30 min)
- **Semantic Similarity**: Similar commit messages or code patterns
- **Dependency Chain**: Changes that build upon each other

#### 3.1.3 AI-Powered Message Generation
- **Providers**: OpenAI (GPT-4, GPT-3.5), Anthropic (Claude), Local (Ollama)
- **Auto-detection**: Intelligent fallback chain with graceful degradation
- **Template fallback**: Works offline without any AI providers
- **Conventional commits**: Follows conventional commit standards

#### 3.1.4 Proactive Safety System
- **Auto-stashing**: Uncommitted changes automatically stashed
- **Auto-branch switching**: Resolves detached HEAD state
- **Auto-file staging**: Stages important untracked files, ignores build artifacts
- **Automatic backups**: Creates safety branches before operations
- **Comprehensive validation**: Checks git state, merge conflicts, etc.

#### 3.1.5 Confidence-Based Execution
- **High confidence (80%+)**: Auto-applies changes immediately
- **Medium confidence (60-80%)**: Asks for user confirmation
- **Low confidence (<60%)**: Forces manual review
- **Critical warnings**: Always blocks auto-execution for safety

#### 3.1.6 Error Recovery System
- **Missing branches**: Tries alternatives (master, develop, dev)
- **API failures**: Falls back to template messages
- **Network issues**: Switches to offline mode
- **Connection errors**: Handles service unavailability gracefully

### 3.2 Configuration System

#### 3.2.1 Traditional Configuration
```yaml
# .git-smart-squash.yml
grouping:
  time_window: 1800  # seconds
  min_file_overlap: 1  # minimum shared files
  similarity_threshold: 0.7  # for semantic matching

commit_format:
  types: [feat, fix, docs, style, refactor, test, chore]
  scope_required: false
  max_subject_length: 50
  body_required: false

ai:
  provider: local  # openai, anthropic, local
  model: devstral  # gpt-4, claude-3-sonnet, devstral
  api_key_env: OPENAI_API_KEY
  base_url: http://localhost:11434  # for local models
  
output:
  dry_run_default: true
  backup_branch: true
  force_push_protection: true
```

#### 3.2.2 Zero-Friction Auto-Configuration
- **AI Provider Detection**: Automatic based on availability
- **Repository Analysis**: Adapts settings to commit patterns
- **Smart Defaults**: No configuration files required
- **Override Capability**: CLI arguments override auto-detection

## 4. Technical Architecture

### 4.1 Component Structure
```
git_smart_squash/
├── analyzer/
│   ├── commit_parser.py          # Git command wrapper
│   ├── diff_analyzer.py          # Code diff analysis
│   └── metadata_extractor.py     # Commit metadata
├── grouping/
│   ├── strategies/
│   │   ├── file_overlap.py       # File-based grouping
│   │   ├── temporal.py           # Time-based grouping
│   │   ├── semantic.py           # Similarity-based grouping
│   │   └── dependency.py         # Dependency chain detection
│   ├── grouping_engine.py        # Strategy orchestration
│   └── utils.py                  # Grouping utilities
├── ai/
│   ├── providers/
│   │   ├── openai.py             # OpenAI GPT integration
│   │   ├── anthropic.py          # Anthropic Claude integration
│   │   └── local.py              # Local model support (Ollama)
│   ├── base.py                   # Provider interface
│   └── message_generator.py      # AI message generation
├── git_operations/
│   ├── rebase_executor.py        # Git rebase operations
│   └── safety_checks.py         # Git state validation
├── utils/
│   └── message.py               # Message utilities
├── zero_friction.py             # Zero-friction UX engine
├── zero_friction_cli.py         # Zero-friction CLI interface
├── cli.py                       # Traditional CLI interface
├── config.py                    # Configuration management
├── models.py                    # Data models
└── constants.py                 # Configuration constants
```

### 4.2 Data Models
```python
@dataclass
class GitCommit:
    hash: str
    short_hash: str
    author: str
    email: str
    timestamp: datetime
    message: str
    files: List[str]
    insertions: int
    deletions: int
    diff: str
    parent_hash: str

@dataclass
class CommitGroup:
    id: str
    commits: List[GitCommit]
    rationale: str
    suggested_message: str
    commit_type: str
    scope: Optional[str]
    files_touched: Set[str]
    total_insertions: int
    total_deletions: int

@dataclass
class Config:
    grouping: GroupingConfig
    commit_format: CommitFormatConfig
    ai: AIConfig
    output: OutputConfig

@dataclass
class AIConfig:
    provider: str  # 'openai', 'anthropic', 'local'
    model: str
    api_key_env: str
    base_url: Optional[str]
```

### 4.3 Zero-Friction Engine

#### 4.3.1 ZeroFrictionEngine Class
```python
class ZeroFrictionEngine:
    def get_smart_defaults(self) -> Config
    def auto_fix_safety_issues(self) -> Tuple[bool, List[str]]
    def calculate_confidence_score(self, groups, warnings) -> float
    def should_auto_execute(self, groups, warnings) -> Tuple[bool, str]
    def auto_recover_from_error(self, error) -> Tuple[bool, str]
```

#### 4.3.2 Auto-Detection Algorithms
```python
def _detect_ai_provider(self):
    # Priority: Ollama → OpenAI → Anthropic → Templates
    # Checks: Service availability, API keys, model availability

def _detect_grouping_preferences(self):
    # Analyzes: Recent commit frequency, repository size
    # Optimizes: Time windows, similarity thresholds

def _filter_important_untracked_files(self, files):
    # Includes: Source files (.py, .js, .ts, etc.)
    # Excludes: Build artifacts, logs, temporary files
```

## 5. Command-Line Interfaces

### 5.1 Zero-Friction CLI Entry Points
```bash
# Package installation creates both commands
pip install git-smart-squash

# Zero-friction interface (recommended)
gss

# Traditional interface (power users)
git-smart-squash
```

### 5.2 Zero-Friction Command Examples
```bash
# Typical usage - just works
gss

# Preview mode for cautious users
gss --preview

# Force mode for override low confidence
gss --force

# Different base branch
gss --base develop

# Check repository readiness
gss status
```

### 5.3 Traditional Command Examples
```bash
# Full configuration control
git-smart-squash --base develop --provider openai --model gpt-4

# Custom grouping strategies
git-smart-squash --strategies file_overlap temporal

# Configuration management
git-smart-squash config --init
git-smart-squash config --show

# Advanced options
git-smart-squash --dry-run --output custom-script.sh
git-smart-squash --no-ai --time-window 3600
```

## 6. Non-Functional Requirements

### 6.1 Performance
- Process 100 commits in < 5 seconds (excluding AI calls)
- AI message generation < 2 seconds per group (local models)
- Interactive UI responsive (< 100ms for user actions)
- Zero-friction startup < 1 second

### 6.2 Reliability
- **Graceful degradation**: AI → Templates → Manual
- **Comprehensive error recovery**: Automatic fallbacks for common failures
- **Safety first**: Automatic backups, validation, dry-run defaults
- **Robust git operations**: Handles merge commits, binary files, edge cases

### 6.3 Usability

#### 6.3.1 Zero-Friction Experience
- **Zero configuration**: Works immediately after installation
- **Intelligent automation**: Minimal user decisions required
- **Clear feedback**: Simple success/failure messages
- **Confidence transparency**: Shows reasoning for decisions

#### 6.3.2 Traditional Experience
- **Full control**: Extensive configuration options
- **Detailed output**: Comprehensive tables and analysis
- **Interactive review**: Manual approval for all operations
- **Power user features**: Advanced grouping strategies

### 6.4 Security
- **No credential storage**: Environment variables only
- **Local-first option**: Ollama support for privacy
- **Sanitized AI inputs**: Safe data submission to external APIs
- **Backup protection**: Automatic safety branches

## 7. Implementation Status

### 7.1 Completed Features ✅
- **Core Architecture**: All components implemented and tested
- **Dual CLI Interface**: Both zero-friction and traditional CLIs working
- **AI Integration**: OpenAI, Anthropic, and Ollama support
- **Grouping Strategies**: All 4 strategies implemented
- **Safety Systems**: Comprehensive validation and backup
- **Error Recovery**: Automatic fallbacks for common failures
- **Configuration Management**: Full config system with precedence
- **Zero-Friction Engine**: Complete auto-detection and confidence system

### 7.2 Current Capabilities
- **Commit Analysis**: Complete parsing and metadata extraction
- **Intelligent Grouping**: File overlap, temporal, semantic, dependency
- **Message Generation**: AI-powered with template fallbacks
- **Safety Validation**: Proactive issue resolution
- **Script Generation**: Safe rebase script output
- **Status Checking**: Repository readiness validation

### 7.3 Production Ready ✅
- **Backward Compatibility**: Original interface unchanged
- **Zero Breaking Changes**: Existing workflows continue working
- **Comprehensive Testing**: All components validated
- **Error Handling**: Robust failure recovery
- **Documentation**: Complete specifications and examples

## 8. Future Enhancements

### 8.1 Direct Git Operations
- **Interactive Rebase Execution**: Direct git operations instead of scripts
- **Real-time Feedback**: Progress indicators during rebase
- **Conflict Resolution**: Automatic handling of simple conflicts

### 8.2 Advanced AI Features
- **Custom Model Training**: Project-specific message generation
- **Multi-modal Analysis**: Code + comments + documentation context
- **Learning System**: Adaptation based on user corrections

### 8.3 Integration Capabilities
- **IDE Extensions**: VS Code, JetBrains integration
- **Git Hooks**: Automatic cleanup on push
- **CI/CD Integration**: Automated commit cleanup in pipelines
- **Platform Integration**: GitHub, GitLab native support

## 9. Success Metrics

### 9.1 Zero-Friction Goals
- **Setup Time**: 0 seconds (auto-configuration)
- **User Decisions**: 0 for 90% of use cases
- **Time to Clean**: < 10 seconds for typical repositories
- **Error Recovery**: 95% automatic resolution

### 9.2 Traditional Goals
- **Commit Reduction**: 70% fewer commits in PRs
- **Time Savings**: 80% faster than manual rebase
- **Message Quality**: 80% AI-generated message acceptance
- **User Adoption**: Seamless migration from existing workflows

### 9.3 Overall Impact
- **Developer Productivity**: Significant time savings on commit cleanup
- **Code Review Quality**: Cleaner, more focused commit histories
- **Adoption Barrier**: Minimal friction for new users
- **Power User Support**: Full control for advanced workflows