"""Unified AI provider implementation."""

import os
import json
import subprocess
from typing import Optional, Dict, Any

from ..core.models import CommitGroup, AIConfig
from .base import BaseAIProvider


class UnifiedAIProvider(BaseAIProvider):
    """Unified AI provider that handles multiple backends."""
    
    def __init__(self, config: AIConfig):
        super().__init__(config.model)
        self.config = config
        self.provider_type = config.provider.lower()
        
        # Provider-specific setup
        if self.provider_type in ["openai", "anthropic"]:
            self.api_key = os.getenv(config.api_key_env)
            if not self.api_key:
                raise ValueError(f"API key not found in environment variable: {config.api_key_env}")
        
        # Common parameters
        self.temperature = 0.3
        self.max_tokens = 200
        self.timeout = 10
        
        # Import provider-specific libraries on demand
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate client based on provider type."""
        if self.provider_type == "openai":
            try:
                import openai
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=self.config.base_url if hasattr(self.config, 'base_url') and self.config.base_url else None,
                    timeout=self.timeout
                )
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        elif self.provider_type == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        elif self.provider_type == "local":
            # Local provider doesn't need a client initialization
            pass
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider_type}")
    
    def generate_commit_message(self, group: CommitGroup) -> Optional[str]:
        """Generate a commit message using the configured provider."""
        handlers = {
            "openai": self._generate_openai,
            "anthropic": self._generate_anthropic,
            "local": self._generate_local
        }
        
        handler = handlers.get(self.provider_type)
        if not handler:
            raise ValueError(f"Unknown provider: {self.provider_type}")
        
        try:
            prompt = self._build_prompt(group)
            message = handler(prompt)
            
            if message and self._validate_message(message):
                return message
            return None
            
        except Exception as e:
            # Silently fail to allow fallback
            return None
    
    def _generate_openai(self, prompt: str) -> Optional[str]:
        """Generate using OpenAI API."""
        if not self._client:
            return None
        
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that generates clear, concise git commit messages following conventional commit format. Focus on the 'what' and 'why' of changes, not implementation details."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception:
            return None
    
    def _generate_anthropic(self, prompt: str) -> Optional[str]:
        """Generate using Anthropic API."""
        if not self._client:
            return None
        
        try:
            # Use default model if specified model is old format
            model = self.model
            if model == "claude-3-sonnet-20240229":
                model = "claude-3-5-sonnet-20241022"
            
            response = self._client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.content[0].text.strip()
            
        except Exception:
            return None
    
    def _generate_local(self, prompt: str) -> Optional[str]:
        """Generate using local model (Ollama or llama.cpp)."""
        # Try Ollama API first
        message = self._try_ollama_api(prompt)
        if message:
            return message
        
        # Try Ollama CLI
        message = self._try_ollama_cli(prompt)
        if message:
            return message
        
        # Try llama.cpp
        return self._try_llamacpp(prompt)
    
    def _try_ollama_api(self, prompt: str) -> Optional[str]:
        """Try to generate using Ollama API."""
        try:
            import requests
            
            url = self.config.base_url or "http://localhost:11434"
            response = requests.post(
                f"{url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                        "stop": ["\n\n", "```", "</commit>"]
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return self._extract_commit_message(result.get("response", ""))
                
        except Exception:
            pass
        
        return None
    
    def _try_ollama_cli(self, prompt: str) -> Optional[str]:
        """Try to generate using Ollama CLI."""
        try:
            # Check if ollama is available
            subprocess.run(["ollama", "--version"], capture_output=True, check=True)
            
            # Run generation
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return self._extract_commit_message(result.stdout)
                
        except Exception:
            pass
        
        return None
    
    def _try_llamacpp(self, prompt: str) -> Optional[str]:
        """Try to generate using llama.cpp."""
        try:
            # Common llama.cpp binary names
            for binary in ["llama", "main", "./main"]:
                try:
                    result = subprocess.run(
                        [binary, "-p", prompt, "-n", str(self.max_tokens)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        return self._extract_commit_message(result.stdout)
                        
                except FileNotFoundError:
                    continue
                    
        except Exception:
            pass
        
        return None
    
    def _extract_commit_message(self, response: str) -> Optional[str]:
        """Extract commit message from response."""
        if not response:
            return None
        
        # Clean up the response
        response = response.strip()
        
        # Try to extract from common formats
        if ":" in response:
            # Look for conventional commit format
            lines = response.split('\n')
            for line in lines:
                if ':' in line and any(prefix in line.lower() for prefix in 
                    ['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore']):
                    return line.strip()
        
        # Return first non-empty line
        for line in response.split('\n'):
            cleaned = line.strip()
            if cleaned and not cleaned.startswith('#'):
                return cleaned
        
        return None