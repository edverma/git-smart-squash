#!/usr/bin/env python3
"""
Measure execution time of individual tests to identify slow tests.
"""

import unittest
import time
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TimedTestResult(unittest.TextTestResult):
    """Custom test result that tracks execution time for each test."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_times = []
        self.current_test_start = None
    
    def startTest(self, test):
        """Record start time when test begins."""
        super().startTest(test)
        self.current_test_start = time.time()
    
    def stopTest(self, test):
        """Record test duration when test ends."""
        super().stopTest(test)
        if self.current_test_start:
            duration = time.time() - self.current_test_start
            test_name = f"{test.__class__.__name__}.{test._testMethodName}"
            self.test_times.append((test_name, duration))
            self.current_test_start = None

def main():
    print("Measuring test execution times...")
    print("=" * 80)
    
    # Test files to measure (excluding AI integration)
    test_files = [
        'test_functionality_comprehensive.py',
        'test_patch_corruption_fixes.py',
        # 'test_idempotency.py' is not a unittest file
    ]
    
    all_times = []
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"Skipping {test_file} - file not found")
            continue
            
        print(f"\nRunning tests from {test_file}...")
        
        # Load tests from the file
        loader = unittest.TestLoader()
        module_name = test_file[:-3]  # Remove .py extension
        
        try:
            # Import the module
            module = __import__(module_name)
            suite = loader.loadTestsFromModule(module)
            
            # Run tests with timing
            runner = unittest.TextTestRunner(
                verbosity=0,
                stream=open(os.devnull, 'w'),  # Suppress output
                resultclass=TimedTestResult
            )
            
            result = runner.run(suite)
            
            # Collect times
            for test_name, duration in result.test_times:
                full_name = f"{module_name}.{test_name}"
                all_times.append((full_name, duration))
                
        except Exception as e:
            print(f"Error loading {test_file}: {e}")
    
    # Sort by duration (slowest first)
    all_times.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "=" * 80)
    print("Test Execution Times (sorted by duration)")
    print("=" * 80)
    print(f"{'Test Name':<70} {'Time (s)':>10}")
    print("-" * 80)
    
    total_time = 0
    slow_tests = []
    
    for test_name, duration in all_times:
        total_time += duration
        print(f"{test_name:<70} {duration:>10.2f}")
        
        if duration > 30:
            slow_tests.append((test_name, duration))
    
    print("-" * 80)
    print(f"{'TOTAL':<70} {total_time:>10.2f}")
    print("=" * 80)
    
    if slow_tests:
        print(f"\n⚠️  WARNING: {len(slow_tests)} tests exceed 30 seconds!")
        print("Slow tests:")
        for test_name, duration in slow_tests:
            print(f"  - {test_name}: {duration:.2f}s")
    else:
        print("\n✅ All tests complete within 30 seconds!")
    
    # Show tests that are close to timeout
    close_tests = [(name, dur) for name, dur in all_times if 20 < dur <= 30]
    if close_tests:
        print(f"\n⏱️  Tests close to 30s timeout ({len(close_tests)} tests):")
        for test_name, duration in close_tests:
            print(f"  - {test_name}: {duration:.2f}s")

if __name__ == '__main__':
    main()