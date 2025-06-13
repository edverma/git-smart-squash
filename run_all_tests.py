#!/usr/bin/env python3
"""
Run all tests for the git-smart-squash project.
This script discovers and runs all test files, providing a unified test runner.
"""

import sys
import unittest
import os
import argparse
import time
from datetime import datetime

class TimeoutTestResult(unittest.TextTestResult):
    """Custom test result class that tracks timeout failures."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeouts = []
    
    def addError(self, test, err):
        """Override to track timeout errors separately."""
        exc_type, exc_value, exc_traceback = err
        if exc_type.__name__ == 'TimeoutException':
            self.timeouts.append((test, exc_value))
            # Still add to errors for proper reporting
            super().addError(test, err)
        else:
            super().addError(test, err)

def main():
    parser = argparse.ArgumentParser(description='Run all git-smart-squash tests')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('-f', '--failfast', action='store_true',
                        help='Stop on first failure')
    parser.add_argument('-p', '--pattern', default='test_*.py',
                        help='Test file pattern (default: test_*.py)')
    parser.add_argument('--include-ai', action='store_true',
                        help='Include AI integration tests (requires API keys)')
    parser.add_argument('--include-local', action='store_true',
                        help='Include local model tests (requires Ollama)')
    parser.add_argument('--exclude', nargs='*', default=[],
                        help='Test files to exclude')
    args = parser.parse_args()

    # Start timer
    start_time = time.time()
    
    print(f"{'='*70}")
    print(f"Running git-smart-squash test suite")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test timeout: 30 seconds per test (excluding local AI tests)")
    print(f"{'='*70}\n")

    # Get the directory of this script
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create test loader
    loader = unittest.TestLoader()
    
    # Discover all tests
    all_tests = loader.discover(test_dir, pattern=args.pattern, top_level_dir=test_dir)
    
    # If AI tests should be excluded (default), remove them
    if not args.include_ai and 'test_ai_integration.py' not in args.exclude:
        args.exclude.append('test_ai_integration.py')
        print("Note: Excluding AI integration tests (use --include-ai to run them)\n")
    
    # Filter out excluded tests
    if args.exclude:
        print(f"Excluding: {', '.join(args.exclude)}\n")
        
        # Create a new test suite without excluded tests
        filtered_suite = unittest.TestSuite()
        
        def add_tests_recursive(suite, parent_suite):
            for test in suite:
                if isinstance(test, unittest.TestSuite):
                    add_tests_recursive(test, parent_suite)
                else:
                    # Check if this test is from an excluded file
                    test_file = test.__module__ + '.py'
                    if not any(excluded in test_file for excluded in args.exclude):
                        parent_suite.addTest(test)
        
        add_tests_recursive(all_tests, filtered_suite)
        all_tests = filtered_suite
    
    # Set up test runner with custom result class
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=args.failfast,
        stream=sys.stdout,
        resultclass=TimeoutTestResult
    )
    
    # Pass flags to AI integration tests if included
    if args.include_ai and args.include_local:
        os.environ['TEST_INCLUDE_LOCAL'] = '1'
        print("Note: Including local model tests\n")
    
    # Run tests
    result = runner.run(all_tests)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Test Summary")
    print(f"{'='*70}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if hasattr(result, 'timeouts') and result.timeouts:
        print(f"Timeouts: {len(result.timeouts)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"{'='*70}\n")
    
    # Report timeout details if any
    if hasattr(result, 'timeouts') and result.timeouts:
        print(f"⏱️  Tests that timed out:")
        for test, error in result.timeouts:
            print(f"  - {test}: {error}")
        print()
    
    # Exit with appropriate code
    if result.wasSuccessful():
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()