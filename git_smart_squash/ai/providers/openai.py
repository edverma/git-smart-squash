"""OpenAI provider for commit message generation."""

import os
import json
from typing import Dict, Any, Optional
from ...models import AIConfig, CommitGroup
from ..base import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider for generating commit messages."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config.model)
        self.config = config
        self.api_key = os.getenv(config.api_key_env)
        if not self.api_key:
            raise ValueError(f"API key not found in environment variable: {config.api_key_env}")
    
    def generate_commit_message(self, group: CommitGroup) -> Optional[str]:
        """Generate a commit message using OpenAI API."""
        try:
            from openai import OpenAI
            
            # Initialize client with custom base URL if provided
            client_kwargs = {"api_key": self.api_key}
            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url
            
            client = OpenAI(**client_kwargs)
            
            prompt = self._build_prompt(group)
            
            response = client.chat.completions.create(
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
            
            # Validate the message
            if self._validate_message(message):
                return message
            else:
                # If validation fails, return None to use fallback
                return None
            
        except ImportError:
            raise RuntimeError("OpenAI library not installed. Install with: pip install openai")
        except Exception as e:
            # Return None on error to use fallback
            return None
    
    # Use the base class _build_prompt method which is already well-structured