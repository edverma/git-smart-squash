"""Prompt building utilities for AI analysis."""

from typing import List, Optional
from ..diff_parser import Hunk


def build_hunk_prompt(hunks: List[Hunk], custom_instructions: Optional[str] = None) -> str:
    parts = [
        "Analyze these code changes and organize them into logical commits for pull request review.",
        "",
        "Each change is represented as a 'hunk' with a unique ID. Group related hunks together",
        "based on functionality, not just file location. A single commit can contain hunks from",
        "multiple files if they implement the same feature or fix.",
        "",
    ]

    if custom_instructions:
        parts.extend(["CUSTOM INSTRUCTIONS FROM USER:", custom_instructions, ""])

    parts.extend([
        "For each commit, provide:",
        "1. A properly formatted git commit message following these rules:",
        "   - First line: max 80 characters (type: brief description)",
        "   - If more detail needed: empty line, then body with lines max 80 chars",
        "   - Use conventional commit format: feat:, fix:, docs:, test:, refactor:, etc.",
        "2. The specific hunk IDs that should be included (not file paths!)",
        "3. A brief rationale for why these changes belong together",
        "",
        "Return your response in this exact structure:",
        "{",
        '  "commits": [',
        "    {",
        '      "message": "feat: add user authentication system\\n\\nImplemented JWT-based authentication with refresh tokens.\\nAdded user model with secure password hashing.",',
        '      "hunk_ids": ["auth.py:45-89", "models.py:23-45", "auth.py:120-145"],',
        '      "rationale": "Groups authentication functionality together"',
        "    }",
        "  ]",
        "}",
        "",
        "IMPORTANT:",
        "- Use hunk_ids (not files) and group by logical functionality",
        "- First line of commit message must be under 80 characters",
        "- Provide rationale for grouping",
        "",
        "CODE CHANGES TO ANALYZE:",
    ])

    for hunk in hunks:
        parts.extend([
            f"Hunk ID: {hunk.id}",
            f"File: {hunk.file_path}",
            f"Context lines: {hunk.start_line}-{hunk.end_line}",
            "",
            "Context:",
            hunk.context if hunk.context else f"(Context unavailable for {hunk.file_path})",
            "",
            "Changes:",
            hunk.content,
            "",
            "---",
            "",
        ])

    return "\n".join(parts)

