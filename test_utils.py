"""
Utilities for test files including timeout decorator.
"""

import signal
import functools
import unittest
import sys
import os

class TimeoutException(Exception):
    """Exception raised when a test times out."""
    pass

def timeout(seconds=30):
    """
    Decorator to add a timeout to test methods.
    Default timeout is 30 seconds.
    
    Note: This uses SIGALRM which is only available on Unix-like systems.
    On Windows, tests will run without timeout.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Skip timeout on Windows
            if sys.platform == 'win32':
                return func(*args, **kwargs)
            
            def timeout_handler(signum, frame):
                raise TimeoutException(f"Test {func.__name__} timed out after {seconds} seconds")
            
            # Set up the timeout
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel the alarm and restore the old handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result
        
        return wrapper
    return decorator

def skip_if_ci():
    """Skip test if running in CI environment."""
    return unittest.skipIf(
        os.getenv('CI') or os.getenv('GITHUB_ACTIONS'),
        "Skipping in CI environment"
    )

def skip_slow_test():
    """Skip slow tests unless SLOW_TESTS env var is set."""
    return unittest.skipIf(
        not os.getenv('SLOW_TESTS'),
        "Skipping slow test (set SLOW_TESTS=1 to run)"
    )