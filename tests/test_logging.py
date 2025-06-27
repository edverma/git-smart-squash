#!/usr/bin/env python3
"""Direct test of the logging functionality"""

import sys
import os

# Add the parent directory to path for direct testing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from git_smart_squash.logger import get_logger, LogLevel
from git_smart_squash.diff_parser import Hunk
from rich.console import Console

def test_logging():
    """Test the logging functionality directly"""
    console = Console()
    logger = get_logger()
    logger.set_console(console)
    
    print("=== Testing Logging Levels ===\n")
    
    # Test INFO level (default)
    print("1. Testing INFO level (default):")
    logger.info("This is an info message")
    logger.debug("This debug message should NOT appear")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print("\n2. Testing DEBUG level:")
    logger.set_level(LogLevel.DEBUG)
    logger.debug("This debug message SHOULD appear")
    logger.hunk_debug("This is a hunk-specific debug message")
    
    print("\n3. Testing patch debug:")
    sample_patch = """diff --git a/test.py b/test.py
index 123..456 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    print("hello")
+    print("hello world")
+    # Added comment
     return True"""
    
    logger.patch_debug(sample_patch)
    
    print("\n4. Testing hunk application messages:")
    logger.hunk_debug("Attempting to apply 3 hunks for commit: feat: add new feature")
    logger.hunk_debug("Hunk IDs: ['hunk1', 'hunk2', 'hunk3']")
    logger.hunk_debug("Hunk application result: failed")
    logger.error("Git apply --cached also failed: error: patch does not apply")
    logger.hunk_debug("Common reasons for patch failure:")
    logger.hunk_debug("  - Hunk context doesn't match current file state")
    logger.hunk_debug("  - File has been modified since diff was generated")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_logging()