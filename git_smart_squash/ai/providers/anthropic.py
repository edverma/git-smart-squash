"""Anthropic Claude provider for commit message generation."""

import os
from typing import Dict, Any, Optional
from ...models import AIConfig, CommitGroup
from ..base import BaseAIProvider


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude API provider for generating commit messages."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config.model or "claude-3-haiku-20240307")
        self.config = config
        self.api_key = os.getenv(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {config.api_key_env}")
    
    def generate_commit_message(self, group: CommitGroup) -> Optional[str]:
        """Generate a commit message using Anthropic Claude API."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            prompt = self._build_prompt(group)
            
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
            
            # Validate the message
            if self._validate_message(message):
                return message
            else:
                return None
            
        except ImportError:
            raise RuntimeError("Anthropic library not installed. Install with: pip install anthropic")
        except Exception as e:
            # Return None on error to use fallback
            return None
    
    # Use the base class _build_prompt method