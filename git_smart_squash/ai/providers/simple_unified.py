"""Simplified unified AI provider."""

import os
import subprocess
import json
import re
from typing import Optional


class UnifiedAIProvider:
    """Simplified unified AI provider."""
    
    MAX_CONTEXT_TOKENS = 12000
    MAX_PREDICT_TOKENS = 12000
    
    def __init__(self, config):
        self.config = config
        self.provider_type = config.ai.provider.lower()
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using simple heuristics."""
        # Rough estimation: 1 token ≈ 4 characters for English text
        # This is conservative and works reasonably well for most models
        return max(1, len(text) // 4)
    
    def _calculate_dynamic_params(self, prompt: str) -> dict:
        """Calculate optimal token parameters based on prompt size for any provider."""
        prompt_tokens = self._estimate_tokens(prompt)
        
        # Set context size based on prompt length, with safety margin
        context_needed = prompt_tokens + 1000  # Extra buffer for response
        max_tokens = min(context_needed, self.MAX_CONTEXT_TOKENS)
        
        # Set prediction tokens based on expected response size
        # For commit organization, we expect structured JSON responses
        response_tokens = min(2000, self.MAX_PREDICT_TOKENS)
        
        return {
            "prompt_tokens": prompt_tokens,
            "max_tokens": max_tokens,
            "response_tokens": response_tokens,
            "context_needed": context_needed
        }
    
    def _calculate_ollama_params(self, prompt: str) -> dict:
        """Calculate optimal num_ctx and num_predict for Ollama based on prompt size."""
        params = self._calculate_dynamic_params(prompt)
        
        return {
            "num_ctx": params["max_tokens"],
            "num_predict": params["response_tokens"]
        }
        
    def generate(self, prompt: str) -> str:
        """Generate response using the configured AI provider."""
        
        if self.provider_type == "local":
            return self._generate_local(prompt)
        elif self.provider_type == "openai":
            return self._generate_openai(prompt)
        elif self.provider_type == "anthropic":
            return self._generate_anthropic(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider_type}")
    
    def _generate_local(self, prompt: str) -> str:
        """Generate using local Ollama with proper token limits."""
        try:
            # Calculate optimal parameters based on prompt size
            ollama_params = self._calculate_ollama_params(prompt)
            
            payload = {
                "model": self.config.ai.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": ollama_params["num_ctx"],
                    "num_predict": ollama_params["num_predict"],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
            
            # Increase timeout for large contexts - be more generous for integration tests
            timeout = 600 if ollama_params["num_ctx"] > 8000 else 300
            
            result = subprocess.run([
                "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload)
            ], capture_output=True, text=True, timeout=timeout)
            
            if result.returncode != 0:
                raise Exception(f"Ollama request failed: {result.stderr}")
            
            response = json.loads(result.stdout)
            
            # Check if response was truncated
            response_text = response.get('response', '')
            if response.get('done', True) is False:
                print(f"Warning: Response may have been truncated. Used {ollama_params['num_ctx']} context tokens.")
            
            return response_text
            
        except subprocess.TimeoutExpired:
            raise Exception(f"Ollama request timed out after {timeout} seconds. Try reducing diff size or using a faster model.")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Ollama: {e}")
        except Exception as e:
            raise Exception(f"Local AI generation failed: {e}")
    
    def _generate_openai(self, prompt: str) -> str:
        """Generate using OpenAI API with dynamic token management."""
        try:
            import openai
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise Exception("OPENAI_API_KEY environment variable not set")
            
            # Calculate dynamic parameters
            params = self._calculate_dynamic_params(prompt)
            
            # Warn if prompt is very large
            if params["prompt_tokens"] > 10000:
                print(f"Warning: Large prompt ({params['prompt_tokens']} tokens). Response may be truncated.")
            
            client = openai.OpenAI(api_key=api_key)
            
            # Use dynamic max_tokens, capped at API limits
            max_tokens = min(params["response_tokens"], 4096)  # OpenAI API limit for responses
            
            response = client.chat.completions.create(
                model=self.config.ai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            # Check if response was truncated
            if response.choices[0].finish_reason == "length":
                print(f"Warning: OpenAI response truncated at {max_tokens} tokens. Consider reducing diff size.")
            
            return response.choices[0].message.content
            
        except ImportError:
            raise Exception("OpenAI library not installed. Run: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI generation failed: {e}")
    
    def _generate_anthropic(self, prompt: str) -> str:
        """Generate using Anthropic API with dynamic token management."""
        try:
            import anthropic
            
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise Exception("ANTHROPIC_API_KEY environment variable not set")
            
            # Calculate dynamic parameters
            params = self._calculate_dynamic_params(prompt)
            
            # Warn if prompt is very large
            if params["prompt_tokens"] > 150000:  # Claude's context limit is ~200k tokens
                print(f"Warning: Large prompt ({params['prompt_tokens']} tokens). May approach Claude's context limit.")
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Use dynamic max_tokens, capped at API limits
            max_tokens = min(params["response_tokens"], 4096)  # Claude API limit for responses
            
            response = client.messages.create(
                model=self.config.ai.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Check if response was truncated
            if response.stop_reason == "max_tokens":
                print(f"Warning: Anthropic response truncated at {max_tokens} tokens. Consider reducing diff size.")
            
            return response.content[0].text
            
        except ImportError:
            raise Exception("Anthropic library not installed. Run: pip install anthropic")
        except Exception as e:
            raise Exception(f"Anthropic generation failed: {e}")