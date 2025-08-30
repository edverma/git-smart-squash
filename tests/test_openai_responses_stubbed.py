import os
import sys
import json
import types
import unittest

from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, AttributionConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider


class TestOpenAIResponsesStubbed(unittest.TestCase):
    def setUp(self):
        # Prepare config forcing OpenAI GPT-5 and reasoning
        self.cfg = Config(
            ai=AIConfig(provider='openai', model='gpt-5', reasoning='high'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        self.provider = UnifiedAIProvider(self.cfg)

        # Stub openai module in sys.modules before import inside provider method
        self.captured = {}
        captured = self.captured

        class FakeResponse:
            def __init__(self):
                # Provider expects a JSON string content
                self.output_text = json.dumps({"commits": [{"message": "ok", "hunk_ids": [], "rationale": "r"}]})

        class FakeClient:
            def __init__(self, api_key=None):
                self.responses = types.SimpleNamespace(create=self.create)
            def create(self, **kwargs):
                captured['params'] = kwargs
                return FakeResponse()

        class FakeOpenAIModule(types.SimpleNamespace):
            def __init__(self):
                super().__init__(OpenAI=lambda api_key=None: FakeClient())

        self._prev_openai = sys.modules.get('openai')
        sys.modules['openai'] = FakeOpenAIModule()
        os.environ['OPENAI_API_KEY'] = 'test-key'

    def tearDown(self):
        # Restore any previous openai module
        if self._prev_openai is None:
            sys.modules.pop('openai', None)
        else:
            sys.modules['openai'] = self._prev_openai

    def test_responses_api_parameters_and_output(self):
        result = self.provider._generate_openai('hello world')

        # Output should be JSON string with commits key from json_schema
        parsed = json.loads(result)
        self.assertIn('commits', parsed)
        self.assertIsInstance(parsed['commits'], list)

        # Validate request shape captured for Responses API
        params = self.captured['params']
        self.assertEqual(params.get('model'), 'gpt-5')
        self.assertIn('input', params)
        self.assertIn('max_output_tokens', params)
        self.assertIn('response_format', params)
        self.assertIn('json_schema', params['response_format'])
        self.assertEqual(params.get('reasoning'), {'effort': 'high'})

    def test_minimal_reasoning_omitted(self):
        # Reconfigure with minimal reasoning
        self.provider.config.ai.reasoning = 'minimal'
        result = self.provider._generate_openai('hello world')
        parsed = json.loads(result)
        self.assertIn('commits', parsed)
        # Ensure reasoning param is omitted when minimal
        params = self.captured['params']
        self.assertTrue('reasoning' not in params)


if __name__ == '__main__':
    unittest.main()
