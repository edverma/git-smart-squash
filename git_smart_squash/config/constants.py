"""Constants used throughout the Git Smart Squash application."""

# Commit type definitions
DEFAULT_COMMIT_TYPES = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']

# Time window for temporal grouping (in seconds)
DEFAULT_TIME_WINDOW = 1800  # 30 minutes

# Similarity thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.7
MIN_SIMILARITY_THRESHOLD = 0.5
MAX_SIMILARITY_THRESHOLD = 0.95

# Message length constraints
MAX_SUBJECT_LENGTH = 50
MAX_BODY_LINE_LENGTH = 72

# Grouping constraints
MAX_GROUP_SIZE = 10
MIN_GROUP_SIZE = 2

# Safety check constants
MAX_COMMITS_FOR_SQUASH = 100
MAX_FILES_PER_COMMIT = 50

# AI provider constants
AI_REQUEST_TIMEOUT = 30  # seconds
AI_MAX_RETRIES = 3
AI_RETRY_DELAY = 1  # seconds

# Display constants
CONSOLE_WIDTH = 80
PROGRESS_UPDATE_INTERVAL = 0.1  # seconds