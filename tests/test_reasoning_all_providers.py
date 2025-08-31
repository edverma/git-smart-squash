import os
import sys
import json
import types
import unittest
from unittest.mock import patch, MagicMock

from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, AttributionConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider


class TestReasoningAllProviders(unittest.TestCase):
    """Test that reasoning effort parameter is properly applied to all provider types."""
    
    def test_openai_reasoning_parameter(self):
        """Test OpenAI provider applies reasoning effort correctly."""
        cfg = Config(
            ai=AIConfig(provider='openai', model='gpt-5', reasoning='high'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        provider = UnifiedAIProvider(cfg)
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            # Create mock openai module
            class FakeResponse:
                output_text = json.dumps({"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]})
            
            # Store spy reference outside
            create_spy = MagicMock(return_value=FakeResponse())
            
            class FakeClient:
                def __init__(self, api_key=None):
                    self.responses = types.SimpleNamespace()
                    self.responses.create = create_spy
            
            fake_openai = types.SimpleNamespace(OpenAI=FakeClient)
            
            with patch.dict(sys.modules, {'openai': fake_openai}):
                # Test high reasoning
                result = provider._generate_openai('test prompt')
                call_args = create_spy.call_args[1]
                self.assertEqual(call_args['reasoning'], {'effort': 'high'})
                
                # Test minimal reasoning
                provider.config.ai.reasoning = 'minimal'
                result = provider._generate_openai('test prompt')
                call_args = create_spy.call_args[1]
                self.assertEqual(call_args['reasoning'], {'effort': 'minimal'})
                
                # Test medium reasoning
                provider.config.ai.reasoning = 'medium'
                result = provider._generate_openai('test prompt')
                call_args = create_spy.call_args[1]
                self.assertEqual(call_args['reasoning'], {'effort': 'medium'})
    
    def test_anthropic_reasoning_parameter(self):
        """Test Anthropic provider applies reasoning effort as thinking budget."""
        cfg = Config(
            ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514', reasoning='high'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        provider = UnifiedAIProvider(cfg)
        
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            # Create mock anthropic module
            class FakeContent:
                type = "tool_use"
                name = "commit_organizer"
                input = {"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]}
            
            class FakeResponse:
                content = [FakeContent()]
            
            # Store spy reference outside
            create_spy = MagicMock(return_value=FakeResponse())
            
            class FakeClient:
                def __init__(self, api_key=None):
                    self.messages = types.SimpleNamespace()
                    self.messages.create = create_spy
            
            fake_anthropic = types.SimpleNamespace(Anthropic=FakeClient)
            
            with patch.dict(sys.modules, {'anthropic': fake_anthropic}):
                # Test high reasoning (should add beta header)
                result = provider._generate_anthropic('test prompt')
                call_args = create_spy.call_args[1]
                self.assertIn('extra_headers', call_args)
                self.assertEqual(call_args['extra_headers']['anthropic-beta'], 'interleaved-thinking-2025-05-14')
                
                # Test minimal reasoning
                provider.config.ai.reasoning = 'minimal'
                result = provider._generate_anthropic('test prompt')
                call_args = create_spy.call_args[1]
                self.assertIn('extra_headers', call_args)
                
                # Test medium reasoning
                provider.config.ai.reasoning = 'medium'
                result = provider._generate_anthropic('test prompt')
                call_args = create_spy.call_args[1]
                self.assertIn('extra_headers', call_args)
    
    def test_gemini_reasoning_parameter(self):
        """Test Gemini provider applies reasoning effort as thinking budget."""
        cfg = Config(
            ai=AIConfig(provider='gemini', model='gemini-2.5-pro', reasoning='high'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        provider = UnifiedAIProvider(cfg)
        
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}):
            # Mock the new API
            class FakeThinkingConfig:
                def __init__(self, thinking_budget):
                    self.thinking_budget = thinking_budget
            
            class FakeResponseConfig:
                def __init__(self, **kwargs):
                    self.config = kwargs
            
            class FakeGenerateContentConfig:
                ResponseConfig = FakeResponseConfig
                def __init__(self, **kwargs):
                    self.config = kwargs
            
            class FakeResponse:
                text = json.dumps({"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]})
            
            generate_spy = MagicMock(return_value=FakeResponse())
            
            class FakeModels:
                def generate_content(self, model, contents, config=None):
                    generate_spy(model, contents, config)
                    return FakeResponse()
            
            class FakeClient:
                def __init__(self, api_key=None):
                    self.models = FakeModels()
            
            fake_genai = types.SimpleNamespace(
                Client=FakeClient,
                types=types.SimpleNamespace(
                    ThinkingConfig=FakeThinkingConfig,
                    GenerateContentConfig=FakeGenerateContentConfig
                )
            )
            
            with patch.dict(sys.modules, {'google.genai': fake_genai, 'google': types.SimpleNamespace(genai=fake_genai)}):
                # Test high reasoning (thinking_budget=24576)
                result = provider._generate_gemini('test prompt')
                call_args = generate_spy.call_args[0]
                config = call_args[2]
                self.assertIsNotNone(config)
                self.assertIn('thinking_config', config.config)
                self.assertEqual(config.config['thinking_config'].thinking_budget, 24576)
                
                # Test minimal reasoning (thinking_budget=0, but Pro should use 1024)
                provider.config.ai.reasoning = 'minimal'
                result = provider._generate_gemini('test prompt')
                call_args = generate_spy.call_args[0]
                config = call_args[2]
                # Pro models can't disable thinking, should use low budget
                self.assertEqual(config.config['thinking_config'].thinking_budget, 1024)
                
                # Test medium reasoning (thinking_budget=8192)
                provider.config.ai.reasoning = 'medium'
                result = provider._generate_gemini('test prompt')
                call_args = generate_spy.call_args[0]
                config = call_args[2]
                self.assertEqual(config.config['thinking_config'].thinking_budget, 8192)
                
                # Test Flash model with minimal (should allow 0)
                cfg.ai.model = 'gemini-2.5-flash'
                provider = UnifiedAIProvider(cfg)
                provider.config.ai.reasoning = 'minimal'
                result = provider._generate_gemini('test prompt')
                call_args = generate_spy.call_args[0]
                config = call_args[2]
                # Flash models can disable thinking
                self.assertEqual(config.config['thinking_config'].thinking_budget, 0)
    
    def test_local_reasoning_parameter(self):
        """Test local provider handles reasoning based on model support."""
        # Test with non-gpt-oss model (should log warning)
        cfg = Config(
            ai=AIConfig(provider='local', model='devstral', reasoning='high'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        provider = UnifiedAIProvider(cfg)
        
        with patch('git_smart_squash.ai.providers.simple_unified.subprocess.run') as mock_run:
            with patch('git_smart_squash.ai.providers.simple_unified.logger') as mock_logger:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = json.dumps({
                    "response": json.dumps({"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]}),
                    "done": True
                })
                mock_run.return_value = mock_result
                
                # Test non-gpt-oss model with reasoning (should warn)
                result = provider._generate_local('test prompt')
                call_args = mock_run.call_args[0][0]
                payload = json.loads(call_args[call_args.index('-d') + 1])
                
                # Should use default parameters, not adjust based on reasoning
                self.assertEqual(payload['options']['temperature'], 0.1)
                self.assertEqual(payload['options']['top_p'], 0.95)
                self.assertEqual(payload['options']['top_k'], 20)
                
                # Should have logged warning about unsupported reasoning
                mock_logger.warning.assert_called_with(
                    "Model devstral does not support native reasoning. "
                    "Reasoning parameter 'high' will be ignored. "
                    "Consider using gpt-oss models for native reasoning support."
                )
        
        # Test with gpt-oss model (should add reasoning directive)
        cfg.ai.model = 'gpt-oss:20b'
        provider = UnifiedAIProvider(cfg)
        
        with patch('git_smart_squash.ai.providers.simple_unified.subprocess.run') as mock_run:
            with patch('git_smart_squash.ai.providers.simple_unified.logger') as mock_logger:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = json.dumps({
                    "response": json.dumps({"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]}),
                    "done": True
                })
                mock_run.return_value = mock_result
                
                # Test gpt-oss with high reasoning
                provider.config.ai.reasoning = 'high'
                result = provider._generate_local('test prompt')
                call_args = mock_run.call_args[0][0]
                payload = json.loads(call_args[call_args.index('-d') + 1])
                
                # Should add reasoning directive to prompt
                self.assertIn("Reasoning: high", payload['prompt'])
                
                # Should log debug message about using native reasoning
                mock_logger.debug.assert_any_call("Using gpt-oss model with native reasoning level: high")
                
                # Test minimal reasoning (should map to low)
                provider.config.ai.reasoning = 'minimal'
                result = provider._generate_local('test prompt')
                call_args = mock_run.call_args[0][0]
                payload = json.loads(call_args[call_args.index('-d') + 1])
                
                # Should map minimal to low for gpt-oss
                self.assertIn("Reasoning: low", payload['prompt'])


if __name__ == '__main__':
    unittest.main()