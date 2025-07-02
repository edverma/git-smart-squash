"""
Dependency validation module for ensuring commit plans respect hunk dependencies.
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Tuple
from .diff_parser import Hunk
from .logger import get_logger

logger = get_logger()


@dataclass
class ValidationResult:
    """Result of dependency validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    dependency_graph: Optional[Dict[str, Set[str]]] = None
    

class DependencyValidator:
    """Validates that commit plans respect hunk dependencies."""
    
    def validate_commit_plan(self, commits: List[dict], hunks: List[Hunk]) -> ValidationResult:
        """
        Validates that commit plan respects hunk dependencies.
        
        Args:
            commits: List of commit dictionaries with 'hunk_ids' field
            hunks: List of Hunk objects with dependency information
            
        Returns:
            ValidationResult with success status and error details
        """
        errors = []
        warnings = []
        
        # Build hunk lookup map
        hunk_map = {hunk.id: hunk for hunk in hunks}
        
        # Build hunk_id to commit_index mapping
        hunk_to_commit = {}
        for commit_idx, commit in enumerate(commits):
            for hunk_id in commit.get("hunk_ids", []):
                hunk_to_commit[hunk_id] = commit_idx
        
        # Build dependency graph for debugging
        dependency_graph = {
            hunk.id: hunk.dependencies.copy() 
            for hunk in hunks if hunk.dependencies
        }
        
        # Validate each hunk's dependencies
        for hunk in hunks:
            if not hunk.dependencies:
                continue
                
            hunk_commit_idx = hunk_to_commit.get(hunk.id)
            if hunk_commit_idx is None:
                warnings.append(f"Hunk {hunk.id} not assigned to any commit")
                continue
            
            for dep_id in hunk.dependencies:
                dep_commit_idx = hunk_to_commit.get(dep_id)
                
                if dep_commit_idx is None:
                    errors.append(
                        f"Hunk {hunk.id} depends on {dep_id}, but {dep_id} is not in any commit"
                    )
                elif dep_commit_idx > hunk_commit_idx:
                    # Dependency is in a later commit - this will fail
                    dep_hunk = hunk_map.get(dep_id)
                    file_info = f" (both in {hunk.file_path})" if dep_hunk and dep_hunk.file_path == hunk.file_path else ""
                    errors.append(
                        f"Hunk {hunk.id} in commit #{hunk_commit_idx + 1} depends on "
                        f"{dep_id} which is in later commit #{dep_commit_idx + 1}{file_info}. "
                        f"These hunks must be in the same commit or dependency must come first."
                    )
        
        # Check for circular dependencies between commits
        circular_errors = self._check_circular_dependencies(commits, hunk_map, hunk_to_commit)
        errors.extend(circular_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            dependency_graph=dependency_graph
        )
    
    def _check_circular_dependencies(
        self, 
        commits: List[dict], 
        hunk_map: Dict[str, Hunk],
        hunk_to_commit: Dict[str, int]
    ) -> List[str]:
        """Check for circular dependencies between commits."""
        errors = []
        
        # Build commit-level dependency graph
        commit_deps = {}  # commit_idx -> set of commit indices it depends on
        
        for commit_idx, commit in enumerate(commits):
            commit_deps[commit_idx] = set()
            
            for hunk_id in commit.get("hunk_ids", []):
                hunk = hunk_map.get(hunk_id)
                if not hunk or not hunk.dependencies:
                    continue
                
                for dep_id in hunk.dependencies:
                    dep_commit_idx = hunk_to_commit.get(dep_id)
                    if dep_commit_idx is not None and dep_commit_idx != commit_idx:
                        commit_deps[commit_idx].add(dep_commit_idx)
        
        # Check for cycles using DFS
        def has_cycle_from(start: int, visited: Set[int], rec_stack: Set[int]) -> Optional[List[int]]:
            visited.add(start)
            rec_stack.add(start)
            
            for neighbor in commit_deps.get(start, set()):
                if neighbor not in visited:
                    cycle = has_cycle_from(neighbor, visited, rec_stack)
                    if cycle:
                        return [start] + cycle
                elif neighbor in rec_stack:
                    return [start, neighbor]
            
            rec_stack.remove(start)
            return None
        
        visited = set()
        for commit_idx in range(len(commits)):
            if commit_idx not in visited:
                cycle = has_cycle_from(commit_idx, visited, set())
                if cycle:
                    cycle_str = " -> ".join(f"Commit #{idx + 1}" for idx in cycle)
                    errors.append(f"Circular dependency detected: {cycle_str}")
        
        return errors
