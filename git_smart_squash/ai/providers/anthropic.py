"""Anthropic Claude provider for commit message generation."""

import os
from typing import Dict, Any
from ...models import AIConfig


class AnthropicProvider:
    """Anthropic Claude API provider for generating commit messages."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.api_key = os.getenv(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {config.api_key_env}")
    
    def generate_commit_message(self, context: Dict[str, Any]) -> str:
        """Generate a commit message using Anthropic Claude API."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            prompt = self._build_prompt(context)
            
            response = client.messages.create(
                model=self.config.model or "claude-3-haiku-20240307",
                max_tokens=150,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            message = response.content[0].text.strip()
            return message
            
        except ImportError:
            raise RuntimeError("Anthropic library not installed. Install with: pip install anthropic")
        except Exception as e:
            # Fallback to suggested message on any error
            return context.get('suggested_message', 'chore: Update files')
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for Anthropic Claude."""
        prompt_parts = [
            "You are an expert at writing conventional git commit messages. "
            "Generate a clear, concise commit message that follows the conventional "
            "commit format: type(scope): description.",
            "",
            f"I need to squash {context['commit_count']} commits into one. Here's the information:",
            "",
            f"Suggested type: {context['commit_type']}",
            f"Scope: {context['scope'] or 'none'}",
            f"Files modified: {', '.join(context['files_touched'][:5])}{'...' if len(context['files_touched']) > 5 else ''}",
            f"Total changes: +{context['total_insertions']} lines, -{context['total_deletions']} lines",
            f"Time span: {context['time_span']}",
            "",
            "Original commit messages:"
        ]
        
        for i, msg in enumerate(context['original_messages'][:3]):
            prompt_parts.append(f"{i+1}. {msg}")
        
        if len(context['original_messages']) > 3:
            prompt_parts.append(f"... and {len(context['original_messages']) - 3} more commits")
        
        # Add sample of the diff if available
        if context.get('diffs') and len(context['diffs']) < 2000:
            prompt_parts.extend([
                "",
                "Sample of changes:",
                context['diffs'][:1000] + ("..." if len(context['diffs']) > 1000 else "")
            ])
        
        prompt_parts.extend([
            "",
            "Please generate a single conventional commit message that best summarizes all these changes.",
            "Requirements:",
            "- Use format: type(scope): description",
            "- Keep the description clear and under 50 characters",
            "- Focus on the main purpose/outcome of the changes",
            "- Use present tense, imperative mood (e.g., 'Add feature' not 'Added feature')",
            "",
            "Respond with only the commit message, no explanation:"
        ])
        
        return "\n".join(prompt_parts)