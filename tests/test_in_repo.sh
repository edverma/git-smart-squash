#!/bin/bash
# Script to test git-smart-squash in any git repository

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located (tests directory)
# Then get the parent directory (git-smart-squash root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPT_DIR="$(dirname "$SCRIPT_DIR")"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository!"
        echo "Usage: $0 [path/to/git/repo]"
        echo "If no path is provided, the current directory will be used."
        exit 1
    fi
}

# Function to cleanup on exit
cleanup() {
    if [ -n "$VENV_CREATED" ] && [ -d "$VENV_DIR" ]; then
        print_info "Cleaning up virtual environment..."
        deactivate 2>/dev/null || true
        rm -rf "$VENV_DIR"
    fi
}

# Set up trap to cleanup on exit
trap cleanup EXIT

# Main script
echo -e "${GREEN}=== Git Smart Squash Local Testing Script ===${NC}"
echo

# Check if a repo path was provided
if [ $# -eq 1 ]; then
    TARGET_REPO="$1"
    if [ ! -d "$TARGET_REPO" ]; then
        print_error "Directory $TARGET_REPO does not exist!"
        exit 1
    fi
    cd "$TARGET_REPO"
    print_info "Testing in repository: $TARGET_REPO"
else
    TARGET_REPO=$(pwd)
    print_info "Testing in current directory: $TARGET_REPO"
fi

# Verify it's a git repository
check_git_repo

# Get repository info
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
CURRENT_BRANCH=$(git branch --show-current)
print_info "Repository: $REPO_NAME"
print_info "Current branch: $CURRENT_BRANCH"

# Create a temporary virtual environment
VENV_DIR="/tmp/gss_test_venv_$$"
VENV_CREATED=1

print_info "Creating temporary virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

print_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install git-smart-squash in development mode
print_info "Installing git-smart-squash in development mode..."
pip install -e "$SCRIPT_DIR" > /dev/null 2>&1
print_success "git-smart-squash installed successfully!"

# Verify installation
if ! command -v git-smart-squash &> /dev/null; then
    print_error "git-smart-squash command not found after installation!"
    exit 1
fi

echo
echo -e "${GREEN}=== Testing Options ===${NC}"
echo "1. Test with current uncommitted changes"
echo "2. Test with existing commits on current branch"
echo "3. Create test commits for demonstration"
echo "4. Run custom git-smart-squash command"
echo
read -p "Select option (1-4): " option

case $option in
    1)
        print_info "Testing with current uncommitted changes..."
        if [ -z "$(git status --porcelain)" ]; then
            print_warning "No uncommitted changes found. Creating some test changes..."
            echo "# Test change $(date)" >> README.md
            echo "test_file_$(date +%s).tmp" >> .gitignore
        fi
        
        print_info "Running git-smart-squash with --debug flag..."
        echo
        git-smart-squash --debug --base main || true
        ;;
        
    2)
        print_info "Testing with existing commits..."
        
        # Find the base branch
        BASE_BRANCH="main"
        if ! git show-ref --verify --quiet refs/heads/main; then
            BASE_BRANCH="master"
            if ! git show-ref --verify --quiet refs/heads/master; then
                print_error "Could not find main or master branch"
                read -p "Enter base branch name: " BASE_BRANCH
            fi
        fi
        
        # Check if current branch has commits ahead of base
        COMMITS_AHEAD=$(git rev-list --count "$BASE_BRANCH".."$CURRENT_BRANCH" 2>/dev/null || echo "0")
        if [ "$COMMITS_AHEAD" -eq "0" ]; then
            print_warning "No commits found ahead of $BASE_BRANCH"
            echo "Would you like to create test commits? (y/n)"
            read -p "> " create_commits
            if [ "$create_commits" = "y" ]; then
                option=3
            else
                exit 0
            fi
        else
            print_info "Found $COMMITS_AHEAD commits ahead of $BASE_BRANCH"
            print_info "Running git-smart-squash with --debug flag..."
            echo
            git-smart-squash --debug --base "$BASE_BRANCH" || true
        fi
        ;;
        
    3)
        print_info "Creating test commits for demonstration..."
        
        # Create a test branch
        TEST_BRANCH="test-gss-$(date +%s)"
        git checkout -b "$TEST_BRANCH"
        
        # Create multiple test commits
        print_info "Creating test file changes..."
        
        # Commit 1: Add new feature
        echo "def new_feature():" > test_feature.py
        echo "    return 'This is a new feature'" >> test_feature.py
        git add test_feature.py
        git commit -m "feat: add new feature function"
        
        # Commit 2: Add documentation
        echo "# Test Feature" > test_feature.md
        echo "This is documentation for the test feature" >> test_feature.md
        git add test_feature.md
        git commit -m "docs: add documentation for test feature"
        
        # Commit 3: Fix typo
        echo "def new_feature():" > test_feature.py
        echo "    return 'This is a new feature!'" >> test_feature.py
        git add test_feature.py
        git commit -m "fix: add exclamation mark"
        
        # Commit 4: Add tests
        echo "def test_new_feature():" > test_test_feature.py
        echo "    assert new_feature() == 'This is a new feature!'" >> test_test_feature.py
        git add test_test_feature.py
        git commit -m "test: add unit test for new feature"
        
        print_success "Created 4 test commits"
        print_info "Running git-smart-squash with --debug flag..."
        echo
        git-smart-squash --debug --base "$CURRENT_BRANCH" || true
        
        print_info "Test branch: $TEST_BRANCH"
        print_info "To cleanup: git checkout $CURRENT_BRANCH && git branch -D $TEST_BRANCH"
        ;;
        
    4)
        print_info "Enter your git-smart-squash command (--debug will be added):"
        read -p "> git-smart-squash " custom_args
        echo
        print_info "Running: git-smart-squash --debug $custom_args"
        echo
        git-smart-squash --debug $custom_args || true
        ;;
        
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

echo
print_success "Testing complete!"
echo
echo -e "${YELLOW}What to look for:${NC}"
echo "- ${BLUE}[dim]${NC} messages are DEBUG level logs (only shown with --debug)"
echo "- ${BLUE}[cyan]HUNK:${NC} messages show detailed hunk application info"
echo "- ${YELLOW}[yellow]${NC} messages are warnings"
echo "- ${RED}[red]${NC} messages are errors"
echo "- Patch content is shown in debug mode when applying hunks"
echo
print_info "The virtual environment will be automatically cleaned up on exit."
print_info "To test again, simply run: $0 $TARGET_REPO"