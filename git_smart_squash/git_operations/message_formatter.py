"""Message formatting and validation utilities."""

from typing import Optional


def validate_and_format_message(message: str, max_subject_length: int = 72) -> str:
    """
    Validate and format a commit message following conventional commit guidelines.
    
    Args:
        message: Raw commit message
        max_subject_length: Maximum length for the subject line
        
    Returns:
        Formatted and validated commit message
    """
    if not message:
        return "chore: Update files"
    
    # Clean up the message
    message = message.strip()
    
    # Split into subject and body
    lines = message.split('\n')
    subject = lines[0]
    body_lines = lines[1:] if len(lines) > 1 else []
    
    # Truncate subject if too long
    if len(subject) > max_subject_length:
        subject = _truncate_subject(subject, max_subject_length)
    
    # Ensure conventional commit format
    if ':' not in subject:
        subject = _add_commit_type_prefix(subject)
    
    # Reconstruct message
    if body_lines:
        # Filter out empty lines at the start of body
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        
        if body_lines:
            return subject + '\n\n' + '\n'.join(body_lines)
    
    return subject


def _truncate_subject(subject: str, max_length: int) -> str:
    """Truncate subject line at word boundary."""
    if len(subject) <= max_length:
        return subject
    
    # Leave room for "..."
    target_length = max_length - 3
    
    # Try to truncate at word boundary
    words = subject.split()
    truncated = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > target_length:
            break
        truncated.append(word)
        current_length += len(word) + 1
    
    if truncated:
        return ' '.join(truncated) + "..."
    else:
        return subject[:target_length] + "..."


def _add_commit_type_prefix(subject: str) -> str:
    """Add conventional commit type prefix based on subject content."""
    subject_lower = subject.lower()
    
    # Map of keywords to commit types
    type_mappings = [
        (['add', 'implement', 'create', 'introduce'], 'feat'),
        (['fix', 'resolve', 'correct', 'repair'], 'fix'),
        (['update', 'modify', 'change', 'refactor'], 'refactor'),
        (['remove', 'delete', 'clean'], 'chore'),
        (['test', 'tests', 'testing'], 'test'),
        (['document', 'docs', 'readme'], 'docs'),
        (['style', 'format', 'lint'], 'style'),
    ]
    
    for keywords, commit_type in type_mappings:
        if any(subject_lower.startswith(k) for k in keywords):
            return f"{commit_type}: {subject}"
    
    # Default to chore if no match
    return f"chore: {subject}"


def extract_commit_type(message: str) -> str:
    """Extract the commit type from a conventional commit message."""
    if ':' not in message:
        return 'chore'
    
    parts = message.split(':', 1)
    commit_type = parts[0].strip().lower()
    
    # Remove scope if present: "feat(scope)" -> "feat"
    if '(' in commit_type:
        commit_type = commit_type.split('(')[0]
    
    # Validate against common types
    valid_types = ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'perf', 'ci', 'build']
    
    if commit_type in valid_types:
        return commit_type
    
    return 'chore'