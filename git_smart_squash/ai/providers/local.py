"""Local AI provider for commit message generation."""

import subprocess
import json
from typing import Dict, Any, Optional
from ...models import AIConfig, CommitGroup
from ..base import BaseAIProvider


class LocalProvider(BaseAIProvider):
    """Local AI model provider for generating commit messages."""
    
    def __init__(self, config: AIConfig):
        model_name = config.model or "codellama:7b"
        super().__init__(model_name)
        self.config = config
        self.model_name = model_name
    
    def generate_commit_message(self, group: CommitGroup) -> Optional[str]:
        """Generate a commit message using a local AI model (via Ollama)."""
        try:
            prompt = self._build_prompt(group)
            
            # Try Ollama first
            try:
                message = self._generate_with_ollama(prompt)
                if message and self._validate_message(message):
                    return message
            except Exception:
                pass
            
            # Fallback to other local options
            try:
                message = self._generate_with_llamacpp(prompt)
                if message and self._validate_message(message):
                    return message
            except Exception:
                pass
            
            # Final fallback
            return None
            
        except Exception:
            return None
    
    def _generate_with_ollama(self, prompt: str) -> str:
        """Generate using Ollama API."""
        try:
            import requests
            
            # Use Ollama API
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 100,
                        "stop": ["\n\n", "---", "```"]
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('response', '').strip()
                if content:
                    # Extract just the commit message from the response
                    lines = content.split('\n')
                    # Look for a line that looks like a commit message
                    for line in lines:
                        line = line.strip()
                        if ':' in line and len(line) < 100 and not line.startswith('#'):
                            return line
                    # Fallback to first non-empty line that's not a comment
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and len(line) < 100:
                            return line
                    return lines[0] if lines else ""
            
        except (ImportError, Exception) as e:
            # Fallback to CLI if API fails
            try:
                cmd = ["ollama", "run", self.model_name, prompt]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # Extract just the commit message from the response
                    lines = result.stdout.strip().split('\n')
                    # Look for a line that looks like a commit message
                    for line in lines:
                        line = line.strip()
                        if ':' in line and len(line) < 100 and not line.startswith('#'):
                            return line
                    # Fallback to first non-empty line
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and len(line) < 100:
                            return line
                    return lines[0] if lines else ""
                
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        raise Exception("Ollama generation failed")
    
    def _generate_with_llamacpp(self, prompt: str) -> str:
        """Generate using llama.cpp server."""
        try:
            import requests
            
            # Assume llama.cpp server running on default port
            response = requests.post(
                "http://localhost:8080/completion",
                json={
                    "prompt": prompt,
                    "n_predict": 50,
                    "temperature": 0.3,
                    "stop": ["\n\n"]
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('content', '').strip()
                if content:
                    # Extract commit message
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if ':' in line and len(line) < 100:
                            return line
                    return lines[0] if lines else ""
            
        except (ImportError, Exception):
            pass
        
        raise Exception("llama.cpp generation failed")