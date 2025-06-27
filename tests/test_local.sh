#!/bin/bash
# Test script for git-smart-squash logging improvements

set -e

echo "=== Git Smart Squash Local Testing ==="
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Create a virtual environment for testing
echo -e "${YELLOW}Setting up test environment...${NC}"
python3 -m venv test_env
source test_env/bin/activate

# Install the package in development mode
echo -e "${YELLOW}Installing git-smart-squash in development mode...${NC}"
pip install -e ..

# Create a test repository
TEST_DIR="test_repo_$(date +%s)"
echo -e "${YELLOW}Creating test repository: $TEST_DIR${NC}"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# Initialize git repo
git init
git config user.email "test@example.com"
git config user.name "Test User"

# Create initial commit
echo "# Test Repository" > README.md
git add README.md
git commit -m "Initial commit"

# Create a feature branch
git checkout -b feature/test-logging

# Create multiple files with changes that might cause hunk application issues
echo -e "${YELLOW}Creating test files with potential hunk conflicts...${NC}"

# File 1: Simple changes
cat > file1.py << 'EOF'
def function1():
    print("Original line 1")
    print("Original line 2")
    print("Original line 3")

def function2():
    print("Function 2 original")
    return True

def function3():
    print("Function 3 original")
    return False
EOF

# File 2: File with no newline at end
printf "line1\nline2\nline3" > file2.txt

# File 3: File with mixed line endings
printf "line1\r\nline2\nline3\r\n" > file3.txt

git add .
git commit -m "Add test files"

# Now make various changes
echo -e "${YELLOW}Making changes to create interesting hunks...${NC}"

# Modify file1.py
cat > file1.py << 'EOF'
def function1():
    print("Modified line 1")  # Changed
    print("Original line 2")
    print("Added line 3.5")   # Added
    print("Original line 3")

def function2():
    print("Function 2 modified")  # Changed
    # Added comment
    return True

def function3():
    print("Function 3 original")
    print("Added line in function 3")  # Added
    return False

def function4():  # New function
    print("New function")
    return None
EOF

# Modify file2.txt (still no newline)
printf "line1 modified\nline2\nline3 modified\nline4 added" > file2.txt

# Modify file3.txt
echo -e "line1 modified\r\nline2 kept\r\nline3 modified\r\nline4 added\r\n" > file3.txt

# Create a file that will be deleted
echo "This file will be deleted" > deleteme.txt
git add deleteme.txt
git commit -m "Add file to be deleted"
rm deleteme.txt

# Test different scenarios
echo -e "\n${GREEN}=== Test 1: Basic usage without debug ===${NC}"
git-smart-squash --base main --auto-apply --ai-provider openai || true

echo -e "\n${GREEN}=== Test 2: With debug flag enabled ===${NC}"
git reset --hard HEAD
git-smart-squash --base main --auto-apply --ai-provider openai --debug || true

echo -e "\n${GREEN}=== Test 3: Testing with manual hunk application ===${NC}"
# Create a scenario where some hunks might fail
git reset --hard HEAD
# Make conflicting changes
echo "conflict line" >> file1.py
git add file1.py
git stash

# Apply original changes
git checkout feature/test-logging
git-smart-squash --base main --ai-provider openai --debug || true

echo -e "\n${GREEN}=== Test 4: Check log output for 'skipping commit' messages ===${NC}"
# Look for our new debug messages
if git-smart-squash --base main --debug 2>&1 | grep -q "Hunk application result:"; then
    echo -e "${GREEN}✓ Debug logging is working!${NC}"
else
    echo -e "${RED}✗ Debug logging not found${NC}"
fi

echo -e "\n${YELLOW}Test complete! Check the output above for:${NC}"
echo "1. Detailed hunk application logs when using --debug"
echo "2. 'Skipping commit' messages with explanations"
echo "3. Patch content in debug mode"
echo "4. Error details when hunks fail to apply"

# Cleanup
cd ..
echo -e "\n${YELLOW}To clean up: rm -rf $TEST_DIR${NC}"
echo -e "${YELLOW}To deactivate venv: deactivate${NC}"