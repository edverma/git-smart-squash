# Git Smart Squash - Technical Specification

## 1. Overview

### 1.1 Purpose
Git Smart Squash is a command-line tool that automatically reorganizes messy git commit histories into clean, semantic commits suitable for pull request reviews. It uses AI and heuristics to group related commits and generate meaningful commit messages.

### 1.2 Problem Statement
Developers often create numerous small, work-in-progress commits while developing features. These commits are useful for backup but create noise during code reviews. Manual cleanup using `git rebase -i` is tedious and time-consuming.

### 1.3 Solution
An automated tool that:
- Analyzes commit relationships using multiple signals
- Groups related commits intelligently
- Generates conventional commit messages using AI
- Provides an interactive review process before applying changes

## 2. Functional Requirements

### 2.1 Core Features

#### 2.1.1 Commit Analysis
- **Input**: Range of commits (current branch vs base branch)
- **Processing**:
  - Extract commit metadata (hash, author, timestamp, message)
  - Retrieve file changes for each commit
  - Calculate diff statistics (insertions, deletions)
  - Store full diff content for AI analysis
- **Output**: Structured commit objects with all relevant data

#### 2.1.2 Intelligent Grouping
- **Grouping Criteria**:
  - File overlap: Commits modifying the same files
  - Temporal proximity: Commits within configurable time window (default: 30 min)
  - Semantic similarity: Similar commit messages or code patterns
  - Dependency chain: Changes that build upon each other
- **Algorithms**:
  - Graph-based clustering for file relationships
  - Sliding window for temporal grouping
  - Embedding similarity for semantic matching (optional)

#### 2.1.3 Commit Message Generation
- **Input**: Group of related commits with their diffs
- **Processing**:
  - Aggregate changes across grouped commits
  - Identify primary change type (feat, fix, docs, etc.)
  - Extract key modifications from diffs
- **Output**: Conventional commit message following configured format

#### 2.1.4 Interactive Review
- **Display**:
  - Show proposed groupings with original commits
  - Preview generated commit messages
  - Highlight files affected by each group
- **User Actions**:
  - Accept/reject groupings
  - Split or merge groups
  - Edit generated messages
  - Adjust grouping parameters

### 2.2 Configuration Options
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
  provider: openai  # or anthropic, local
  model: gpt-4
  api_key_env: OPENAI_API_KEY
  
output:
  dry_run_default: true
  backup_branch: true
  force_push_protection: true
```

### 2.3 Command-Line Interface
```bash
# Basic usage
git smart-squash

# Specify base branch
git smart-squash --base develop

# Skip interactive mode
git smart-squash --auto

# Use local AI model
git smart-squash --ai-provider local --model codellama

# Custom config
git smart-squash --config .custom-config.yml

# Output rebase script without executing
git smart-squash --dry-run --output rebase-script.sh
```

## 3. Technical Architecture

### 3.1 Component Structure
```
GitSmartSquash/
├── analyzer/
│   ├── commit_parser.py      # Git command wrapper
│   ├── diff_analyzer.py      # Code diff analysis
│   └── metadata_extractor.py # Commit metadata
├── grouping/
│   ├── strategies/
│   │   ├── file_overlap.py
│   │   ├── temporal.py
│   │   ├── semantic.py
│   │   └── dependency.py
│   └── grouping_engine.py   # Combines strategies
├── ai/
│   ├── providers/
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── local.py
│   └── message_generator.py
├── interactive/
│   ├── tui.py              # Terminal UI (using Rich/Textual)
│   └── reviewer.py         # Review logic
├── git_operations/
│   ├── rebase_executor.py
│   └── safety_checks.py
└── cli.py                  # Entry point
```

### 3.2 Data Models
```python
@dataclass
class Commit:
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
    commits: List[Commit]
    rationale: str  # Why these were grouped
    suggested_message: str
    commit_type: str  # feat, fix, etc.
    scope: Optional[str]
    files_touched: Set[str]
    total_insertions: int
    total_deletions: int

@dataclass
class RebaseOperation:
    action: str  # pick, squash, fixup, drop
    commit: Commit
    target_group: Optional[CommitGroup]
```

### 3.3 Key Algorithms

#### 3.3.1 File-Based Grouping
```python
def group_by_files(commits: List[Commit]) -> List[CommitGroup]:
    # Build file-commit graph
    # Find connected components
    # Return groups based on file overlap
```

#### 3.3.2 Semantic Similarity
```python
def calculate_similarity(commit1: Commit, commit2: Commit) -> float:
    # Option 1: Simple token overlap
    # Option 2: Embedding similarity (requires AI)
    # Option 3: Diff structure similarity
```

#### 3.3.3 AI Message Generation
```python
def generate_message(group: CommitGroup) -> str:
    context = build_context(group)
    prompt = create_prompt(context)
    message = ai_provider.generate(prompt)
    return validate_and_format(message)
```

## 4. Non-Functional Requirements

### 4.1 Performance
- Process 100 commits in < 5 seconds (excluding AI calls)
- AI message generation < 2 seconds per group
- Interactive UI responsive (< 100ms for user actions)

### 4.2 Reliability
- Graceful handling of:
  - Network failures (AI API calls)
  - Malformed commits
  - Binary files
  - Merge commits
- Automatic backup before rebase operations
- Dry-run mode by default

### 4.3 Usability
- Clear progress indicators
- Informative error messages
- Undo capability (git reflog integration)
- Extensive help documentation
- Shell completion support

### 4.4 Security
- No storage of API keys in config files
- Environment variable support for credentials
- Optional local-only mode (no external API calls)
- Sanitization of commit data before AI submission

## 5. Implementation Phases

### Phase 1: MVP (Version 0.1)
- Basic commit analysis
- Simple file-based grouping
- Hardcoded message templates
- CLI with dry-run output

### Phase 2: AI Integration (Version 0.2)
- OpenAI API integration
- Basic prompt engineering
- Message validation
- Configuration file support

### Phase 3: Interactive Mode (Version 0.3)
- Terminal UI for reviewing groups
- Manual group adjustment
- Message editing
- Safety checks

### Phase 4: Advanced Features (Version 0.4)
- Multiple grouping strategies
- Local AI model support
- Dependency analysis
- Performance optimizations

### Phase 5: Polish (Version 1.0)
- Plugin system for custom strategies
- Integration with git hooks
- IDE extensions
- Comprehensive test suite

## 6. Testing Strategy

### 6.1 Unit Tests
- Commit parsing accuracy
- Grouping algorithm correctness
- Message generation validation
- Git command execution

### 6.2 Integration Tests
- End-to-end workflow tests
- AI provider integration
- Git repository operations
- Configuration loading

### 6.3 Test Scenarios
- Repositories with 1-1000 commits
- Various commit patterns (linear, branched)
- Different programming languages
- Edge cases (empty commits, binary files)

## 7. Future Enhancements

### 7.1 Advanced Analysis
- AST-based code analysis for better grouping
- Build system integration (group by build targets)
- Test-implementation coupling detection

### 7.2 Collaboration Features
- Team-shared grouping rules
- PR platform integration (GitHub, GitLab)
- Commit message templates per project

### 7.3 Learning Capabilities
- Learn from user corrections
- Project-specific patterns
- Personalized message style

## 8. Success Metrics

### 8.1 Quantitative
- Reduction in commits per PR (target: 70% reduction)
- Time saved vs manual rebase (target: 80% faster)
- User adoption rate
- AI message acceptance rate (target: > 80%)

### 8.2 Qualitative
- User satisfaction surveys
- Code reviewer feedback
- Community contributions
- Feature requests and usage patterns
