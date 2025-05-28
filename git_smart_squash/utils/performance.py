"""Performance optimization utilities for large repositories."""

import time
import subprocess
from typing import List, Optional
from functools import wraps


class PerformanceOptimizer:
    """Handles performance optimization for large repositories."""
    
    def __init__(self, max_commits: int = 100, timeout_seconds: int = 30):
        self.max_commits = max_commits
        self.timeout_seconds = timeout_seconds
        self.start_time = None
    
    def start_timer(self):
        """Start performance timing."""
        self.start_time = time.time()
    
    def check_timeout(self) -> bool:
        """Check if operation has exceeded timeout."""
        if self.start_time is None:
            return False
        return (time.time() - self.start_time) > self.timeout_seconds
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since start."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
    
    def should_use_fast_mode(self, commit_count: int) -> bool:
        """Determine if fast mode should be used based on repository size."""
        return commit_count > 50
    
    def optimize_git_command(self, cmd: List[str], large_repo: bool = False) -> List[str]:
        """Optimize git command for performance."""
        optimized_cmd = cmd.copy()
        
        if large_repo:
            # Add performance optimizations for large repositories
            if "git" in cmd[0] and "log" in cmd:
                # Limit output for log commands
                if "--max-count" not in " ".join(cmd):
                    optimized_cmd.extend(["--max-count", str(self.max_commits)])
                
                # Skip merge commits for cleaner analysis
                if "--no-merges" not in " ".join(cmd):
                    optimized_cmd.append("--no-merges")
        
        return optimized_cmd


def timeout_wrapper(timeout_seconds: int = 30):
    """Decorator to add timeout to functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            def check_timeout():
                return (time.time() - start_time) > timeout_seconds
            
            # Add timeout check to kwargs if the function accepts it
            if 'timeout_check' in func.__code__.co_varnames:
                kwargs['timeout_check'] = check_timeout
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                # Log performance warning if operation was slow
                if elapsed > timeout_seconds * 0.8:
                    print(f"⚠️  Operation took {elapsed:.1f}s (consider using --preview for large repositories)")
                
                return result
            except Exception as e:
                if check_timeout():
                    raise TimeoutError(f"Operation timed out after {timeout_seconds}s")
                raise e
        
        return wrapper
    return decorator


class RepositoryAnalyzer:
    """Analyzes repository characteristics for performance optimization."""
    
    @staticmethod
    def get_repository_size() -> dict:
        """Get basic repository size metrics."""
        try:
            # Get total commit count
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True, text=True, timeout=5
            )
            total_commits = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            # Get repository size
            result = subprocess.run(
                ["git", "count-objects", "-v"],
                capture_output=True, text=True, timeout=5
            )
            
            size_info = {}
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ' ' in line:
                        key, value = line.split(' ', 1)
                        size_info[key] = value
            
            # Get number of branches
            result = subprocess.run(
                ["git", "branch", "-a"],
                capture_output=True, text=True, timeout=5
            )
            branch_count = len(result.stdout.split('\n')) if result.returncode == 0 else 0
            
            return {
                'total_commits': total_commits,
                'branch_count': branch_count,
                'is_large': total_commits > 1000,
                'size_info': size_info
            }
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
            return {
                'total_commits': 0,
                'branch_count': 0,
                'is_large': False,
                'size_info': {}
            }
    
    @staticmethod
    def should_use_performance_mode(commit_count: int) -> bool:
        """Determine if performance optimizations should be enabled."""
        return commit_count > 50 or RepositoryAnalyzer.get_repository_size()['is_large']


class BatchProcessor:
    """Process operations in batches for better performance."""
    
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
    
    def process_commits_in_batches(self, commits, processor_func):
        """Process commits in batches to avoid memory issues."""
        results = []
        
        for i in range(0, len(commits), self.batch_size):
            batch = commits[i:i + self.batch_size]
            batch_results = processor_func(batch)
            results.extend(batch_results)
            
            # Yield control periodically
            if i % (self.batch_size * 5) == 0:
                time.sleep(0.001)  # Small pause to prevent blocking
        
        return results


# Performance monitoring context manager
class PerformanceMonitor:
    """Context manager for monitoring operation performance."""
    
    def __init__(self, operation_name: str, warn_threshold: float = 10.0):
        self.operation_name = operation_name
        self.warn_threshold = warn_threshold
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            elapsed = time.time() - self.start_time
            
            if elapsed > self.warn_threshold:
                print(f"⚠️  {self.operation_name} took {elapsed:.1f}s")
            elif elapsed > 1.0:
                print(f"ℹ️  {self.operation_name} completed in {elapsed:.1f}s")