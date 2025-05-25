"""OpenAI provider for commit message generation."""

import os
import json
from typing import Dict, Any
from ...models import AIConfig


class OpenAIProvider:
    """OpenAI API provider for generating commit messages."""
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.api_key = os.getenv(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {config.api_key_env}")
    
    def generate_commit_message(self, context: Dict[str, Any]) -> str:
        """Generate a commit message using OpenAI API."""
        try:
            import openai
            openai.api_key = self.api_key
            
            prompt = self._build_prompt(context)
            
            response = openai.ChatCompletion.create(
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at writing conventional git commit messages. "
                                 "Generate clear, concise commit messages that follow the conventional "
                                 "commit format: type(scope): description. Be specific about what "
                                 "changed and why."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=150,
                temperature=0.3,
                timeout=10
            )
            
            message = response.choices[0].message.content.strip()
            return message
            
        except ImportError:
            raise RuntimeError("OpenAI library not installed. Install with: pip install openai")
        except Exception as e:
            # Fallback to suggested message on any error
            return context.get('suggested_message', 'chore: Update files')
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for OpenAI."""
        prompt_parts = [
            f"Generate a conventional commit message for {context['commit_count']} commits that should be squashed together.",
            "",
            f"Suggested type: {context['commit_type']}",
            f"Scope: {context['scope'] or 'none'}",
            f"Files touched: {', '.join(context['files_touched'][:5])}{'...' if len(context['files_touched']) > 5 else ''}",
            f"Changes: +{context['total_insertions']} -{context['total_deletions']}",
            f"Time span: {context['time_span']}",
            "",
            "Original commit messages:"
        ]
        
        for i, msg in enumerate(context['original_messages'][:3]):  # Limit to first 3
            prompt_parts.append(f"{i+1}. {msg}")
        
        if len(context['original_messages']) > 3:
            prompt_parts.append(f"... and {len(context['original_messages']) - 3} more")
        
        # Add key parts of the diff if available and not too long
        if context.get('diffs') and len(context['diffs']) < 2000:
            prompt_parts.extend([
                "",
                "Key changes (excerpt):",
                context['diffs'][:1000] + ("..." if len(context['diffs']) > 1000 else "")
            ])
        
        prompt_parts.extend([
            "",
            "Generate a single, clear conventional commit message that summarizes all these changes.",
            "Format: type(scope): description",
            "Keep the description under 50 characters if possible."
        ])
        
        return "\n".join(prompt_parts)