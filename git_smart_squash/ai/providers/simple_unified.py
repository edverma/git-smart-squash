"""Simplified unified AI provider."""

import os
import subprocess
import json
import google.generativeai as genai
from ...logger import get_logger

logger = get_logger()


class UnifiedAIProvider:
    """Simplified unified AI provider."""
    
    # Provider-specific hard maximum context token limits
    PROVIDER_MAX_CONTEXT_TOKENS = {
        'local': 32000,       # Ollama hard maximum
        'openai': 1000000,    # OpenAI hard maximum (1M tokens)
        'gemini': 1000000,    # Gemini hard maximum (1M tokens)
        'anthropic': 200000   # Anthropic hard maximum (200k tokens)
    }
    
    # Conservative defaults
    DEFAULT_MAX_CONTEXT_TOKENS = 32000
    MAX_PREDICT_TOKENS = 32000
    
    # Schema for commit organization JSON structure  
    COMMIT_SCHEMA = {
        "type": "object",
        "properties": {
            "commits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "hunk_ids": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"}
                    },
                    "required": ["message", "hunk_ids", "rationale"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["commits"],
        "additionalProperties": False
    }
    
    # Gemini-compatible schema (without additionalProperties)
    GEMINI_SCHEMA = {
        "type": "object",
        "properties": {
            "commits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "hunk_ids": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"}
                    },
                    "required": ["message", "hunk_ids", "rationale"]
                }
            }
        },
        "required": ["commits"]
    }
    
    def __init__(self, config):
        self.config = config
        self.provider_type = config.ai.provider.lower()
        # Set provider-specific maximum context tokens
        self.MAX_CONTEXT_TOKENS = self.PROVIDER_MAX_CONTEXT_TOKENS.get(
            self.provider_type, 
            self.DEFAULT_MAX_CONTEXT_TOKENS
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken for all providers."""
        try:
            import tiktoken
            
            # Use tiktoken for all providers - it provides much more accurate 
            # token estimation than character-based heuristics
            # cl100k_base is used by GPT-4, GPT-3.5-turbo and is a good general tokenizer
            encoding = tiktoken.get_encoding('cl100k_base')
            token_count = len(encoding.encode(text))
            # Ensure minimum of 1 token for consistency with fallback behavior
            return max(1, token_count)
                
        except ImportError:
            # Fall back to heuristic if tiktoken not available
            logger.warning("tiktoken not available, using fallback token estimation")
        except Exception as e:
            # Fall back to heuristic on any tiktoken error
            logger.warning(f"tiktoken error ({e}), using fallback token estimation")
        
        # Fallback heuristic only when tiktoken fails
        # More conservative estimation for code/diffs: 1 token ≈ 3 characters
        # This overestimates to ensure we don't truncate prompts
        return max(1, int(len(text) // 3))
    
    def _calculate_dynamic_params(self, prompt: str) -> dict:
        """Calculate optimal token parameters based on prompt size for any provider."""
        prompt_tokens = self._estimate_tokens(prompt)
        
        # Get provider-specific context limit
        provider_limit = self.PROVIDER_MAX_CONTEXT_TOKENS.get(
            self.provider_type, 
            self.DEFAULT_MAX_CONTEXT_TOKENS
        )
        
        # Check if prompt exceeds our maximum supported context
        if prompt_tokens > provider_limit - 2000:  # Reserve 2000 for response
            raise Exception(f"Diff is too large ({prompt_tokens} tokens). Maximum supported: {provider_limit - 2000} tokens. Consider breaking down your changes into smaller commits.")
        
        # Ensure context window is always sufficient for prompt + substantial response buffer
        # Use larger buffer for complex tasks and be more conservative
        response_buffer = max(2000, (prompt_tokens // 3) + 2000)  # Scale buffer with prompt size
        context_needed = prompt_tokens + response_buffer
        
        # Ensure we never exceed hard limits but always accommodate the full prompt
        max_tokens = min(context_needed, provider_limit)
        
        # If context_needed exceeds provider_limit, we must fit within limits
        # but ensure response space is reasonable
        if context_needed > provider_limit:
            # Reserve at least 1000 tokens for response, use rest for prompt
            max_tokens = provider_limit
            response_buffer = min(response_buffer, 1000)
        
        # Set prediction tokens based on expected response size
        response_tokens = min(response_buffer, self.MAX_PREDICT_TOKENS)
        
        return {
            "prompt_tokens": prompt_tokens,
            "max_tokens": max_tokens,
            "response_tokens": response_tokens,
            "context_needed": context_needed
        }
    
    def _calculate_ollama_params(self, prompt: str) -> dict:
        """Calculate optimal num_ctx and num_predict for Ollama based on prompt size."""
        params = self._calculate_dynamic_params(prompt)
        
        # Get the provider-specific limit
        provider_limit = self.PROVIDER_MAX_CONTEXT_TOKENS.get('local', 32000)
        
        # For large prompts, use the full context window to maximize capacity
        # For smaller prompts, optimize for efficiency
        estimated_prompt_tokens = params["prompt_tokens"]
        
        # If the dynamic calculation already uses most of the context window,
        # just use the maximum to avoid weird intermediate values
        if params["max_tokens"] > provider_limit * 0.8:
            num_ctx = provider_limit
        else:
            # Use 15% safety margin since token estimation may be imperfect
            min_context_needed = int(estimated_prompt_tokens * 1.15) + 1000  # 15% safety margin + response space
            num_ctx = max(params["max_tokens"], min_context_needed)
            # Respect absolute maximum
            num_ctx = min(num_ctx, provider_limit)
        
        return {
            "num_ctx": num_ctx,
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
        elif self.provider_type == "gemini":
            return self._generate_gemini(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider_type}")
    
    def _generate_local(self, prompt: str) -> str:
        """Generate using local Ollama with structured output enforcement."""
        try:
            # Calculate optimal parameters based on prompt size
            ollama_params = self._calculate_ollama_params(prompt)
            
            payload = {
                "model": self.config.ai.model,
                "prompt": prompt,
                "stream": False,
                "format": self.COMMIT_SCHEMA,  # Enforce JSON structure
                "options": {
                    "num_ctx": ollama_params["num_ctx"],
                    "num_predict": ollama_params["num_predict"],
                    "temperature": 0.1,  # Lower temperature for more structured output
                    "top_p": 0.95,       # Higher top_p for better instruction following
                    "top_k": 20,         # Lower top_k for more focused responses
                    "repeat_penalty": 1.1,  # Prevent repetitive explanations
                    "stop": ["\n\nHuman:", "User:", "Assistant:", "Note:"]  # Stop conversational patterns
                }
            }
            
            # Increase timeout for large contexts - be more generous for integration tests
            # Scale timeout based on context size to handle very large diffs
            if ollama_params["num_ctx"] > 20000:
                timeout = 7200  # 120 minutes for very large contexts
            elif ollama_params["num_ctx"] > 8000:
                timeout = 1800   # 30 minutes for large contexts
            else:
                timeout = 900   # 15 minutes for normal contexts
            
            result = subprocess.run([
                "curl", "-s", "-X", "POST", "http://localhost:11434/api/generate",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload)
            ], capture_output=True, text=True, timeout=timeout)
            
            if result.returncode != 0:
                if result.returncode == 7:
                    raise Exception("Ollama request failed: Could not connect to Ollama server at localhost:11434. Please ensure Ollama is running.")
                else:
                    raise Exception(f"Ollama request failed: {result.stderr}")
            
            response = json.loads(result.stdout)
            
            # Check if response was truncated
            response_text = response.get('response', '')
            if response.get('done', True) is False:
                logger.warning(f"Response may have been truncated. Used {ollama_params['num_ctx']} context tokens.")
            
            # Parse and ensure correct format
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and "commits" in parsed:
                    return json.dumps(parsed)  # Return full dict
                elif isinstance(parsed, list):
                    # Wrap list in expected format
                    return json.dumps({"commits": parsed})
                else:
                    return response_text
            except json.JSONDecodeError:
                return response_text  # Return as-is if not JSON
            
        except subprocess.TimeoutExpired:
            raise Exception(f"Ollama request timed out after {timeout} seconds. Try reducing diff size or using a faster model.")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Ollama: {e}")
        except Exception as e:
            raise Exception(f"Local AI generation failed: {e}")
    
    def _generate_openai(self, prompt: str) -> str:
        """Generate using OpenAI API with structured output enforcement."""
        try:
            import openai
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise Exception("OPENAI_API_KEY environment variable not set")
            
            # Calculate dynamic parameters
            params = self._calculate_dynamic_params(prompt)
            
            # Use provider-level context limit
            model_context_limit = self.PROVIDER_MAX_CONTEXT_TOKENS.get('openai', 1000000)
            
            # Check if prompt exceeds model context limit
            if params["prompt_tokens"] > model_context_limit - 1000:  # Reserve 1000 for response
                raise Exception(f"Prompt ({params['prompt_tokens']} tokens) exceeds {self.config.ai.model} context limit ({model_context_limit}). Consider reducing diff size.")
            
            # Warn if prompt is large but manageable
            if params["prompt_tokens"] > model_context_limit * 0.7:
                logger.warning(f"Large prompt ({params['prompt_tokens']} tokens) approaching {self.config.ai.model} context limit.")
            
            client = openai.OpenAI(api_key=api_key)
            
            # Use dynamic max_tokens, ensuring total doesn't exceed context limit
            max_response_tokens = min(
                params["response_tokens"], 
                self.MAX_PREDICT_TOKENS,
                model_context_limit - params["prompt_tokens"] - 100  # Safety buffer
            )
            
            response = client.chat.completions.create(
                model=self.config.ai.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_response_tokens,
                temperature=0.7,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "commit_plan",
                        "schema": self.COMMIT_SCHEMA,
                        "strict": True
                    }
                }
            )
            
            # Check if response was truncated
            if response.choices[0].finish_reason == "length":
                logger.warning(f"OpenAI response truncated at {max_response_tokens} tokens. Consider reducing diff size.")
            
            # Return the full structured response
            content = response.choices[0].message.content
            return content  # OpenAI already returns the correct format with json_schema
            
        except ImportError:
            raise Exception("OpenAI library not installed. Run: pip install openai")
        except Exception as e:
            raise Exception(f"OpenAI generation failed: {e}")
    
    def _generate_anthropic(self, prompt: str) -> str:
        """Generate using Anthropic API with structured output enforcement."""
        try:
            import anthropic
            
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise Exception("ANTHROPIC_API_KEY environment variable not set")
            
            # Calculate dynamic parameters
            params = self._calculate_dynamic_params(prompt)
            
            # Use provider-level context limit
            model_context_limit = self.PROVIDER_MAX_CONTEXT_TOKENS.get('anthropic', 200000)
            
            # Check if prompt exceeds model context limit
            if params["prompt_tokens"] > model_context_limit - 4000:  # Reserve 4000 for response
                raise Exception(f"Prompt ({params['prompt_tokens']} tokens) exceeds {self.config.ai.model} context limit ({model_context_limit}). Consider reducing diff size.")
            
            # Warn if prompt is large but manageable
            if params["prompt_tokens"] > model_context_limit * 0.8:
                logger.warning(f"Large prompt ({params['prompt_tokens']} tokens) approaching {self.config.ai.model} context limit.")
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Use dynamic max_tokens, ensuring total doesn't exceed context limit
            max_response_tokens = min(
                params["response_tokens"], 
                self.MAX_PREDICT_TOKENS,
                model_context_limit - params["prompt_tokens"] - 1000  # Safety buffer
            )
            
            # Use tool-based structured output for reliable JSON
            tools = [{
                "name": "commit_organizer",
                "description": "Organize git commits into structured format",
                "input_schema": self.COMMIT_SCHEMA
            }]
            
            response = client.messages.create(
                model=self.config.ai.model,
                max_tokens=max_response_tokens,
                tools=tools,
                tool_choice={"type": "tool", "name": "commit_organizer"},
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract structured data from tool use
            for content in response.content:
                if content.type == "tool_use" and content.name == "commit_organizer":
                    # Return the full structured response, not just the commits array
                    structured_data = content.input
                    return json.dumps(structured_data)
            
            # Fallback if no tool use found
            if response.content and response.content[0].type == "text":
                return response.content[0].text
            
            raise Exception("No valid response content found")
            
        except ImportError:
            raise Exception("Anthropic library not installed. Run: pip install anthropic")
        except Exception as e:
            raise Exception(f"Anthropic generation failed: {e}")
    
    def _generate_gemini(self, prompt: str) -> str:
        """Generate using Google Gemini API with structured output enforcement."""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise Exception("GEMINI_API_KEY environment variable not set")
            
            # Configure the API
            genai.configure(api_key=api_key)
            
            # Calculate dynamic parameters
            params = self._calculate_dynamic_params(prompt)
            
            # Use provider-level context limit
            model_context_limit = self.PROVIDER_MAX_CONTEXT_TOKENS.get('gemini', 1000000)
            
            # Check if prompt exceeds model context limit
            if params["prompt_tokens"] > model_context_limit - 4000:  # Reserve 4000 for response
                raise Exception(f"Prompt ({params['prompt_tokens']} tokens) exceeds {self.config.ai.model} context limit ({model_context_limit}). Consider reducing diff size.")
            
            # Warn if prompt is large but manageable
            if params["prompt_tokens"] > model_context_limit * 0.8:
                logger.warning(f"Large prompt ({params['prompt_tokens']} tokens) approaching {self.config.ai.model} context limit.")
            
            # Create the model
            model = genai.GenerativeModel(self.config.ai.model)
            
            max_response_tokens = min(
                params["response_tokens"], 
                self.MAX_PREDICT_TOKENS,
                model_context_limit - params["prompt_tokens"] - 1000  # Safety buffer
            )
            
            # Configure generation with JSON mode for structured output
            generation_config = genai.types.GenerationConfig(
                candidate_count=1,
                max_output_tokens=max_response_tokens,
                temperature=0.1,  # Lower temperature for more structured output
                top_p=0.95,       # Higher top_p for better instruction following
                top_k=20,         # Lower top_k for more focused responses
                response_mime_type="application/json",  # Force JSON output
                response_schema=self.GEMINI_SCHEMA  # Use Gemini-compatible schema
            )
            
            # Generate response
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # Check if response was blocked
            if response.candidates[0].finish_reason.name in ['SAFETY', 'RECITATION']:
                raise Exception(f"Gemini response blocked due to safety filters: {response.candidates[0].finish_reason}")
            
            # Check if response was truncated
            if response.candidates[0].finish_reason.name == 'MAX_TOKENS':
                raise Exception(f"Gemini response truncated at {max_response_tokens} tokens. Consider reducing diff size or using a model with larger context window.")
            
            # Check if response has no valid parts
            if not response.candidates[0].content.parts:
                raise Exception(f"Gemini response has no content parts. Finish reason: {response.candidates[0].finish_reason}")
            
            # Extract structured data from response
            try:
                response_text = response.text
            except Exception as e:
                raise Exception(f"Failed to extract text from Gemini response: {e}. Finish reason: {response.candidates[0].finish_reason}")
            
            # Parse the JSON response and return the full structure
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and "commits" in parsed:
                    return json.dumps(parsed)  # Return full dict
                elif isinstance(parsed, list):
                    # Wrap list in expected format
                    return json.dumps({"commits": parsed})
                else:
                    return response_text
            except json.JSONDecodeError:
                return response_text  # Return as-is if not JSON
            
        except ImportError:
            raise Exception("Google Generative AI library not installed. Run: pip install google-generativeai")
        except Exception as e:
            raise Exception(f"Google Gemini generation failed: {e}")