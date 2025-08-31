#!/usr/bin/env python3
"""
Stubbed tests for Anthropic and Gemini providers verifying structured
output handling without real network calls.
"""

import json
import os
import sys
import types
import unittest

from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, AttributionConfig
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider


class TestAnthropicStubbed(unittest.TestCase):
    def setUp(self):
        # Prepare config
        self.cfg = Config(
            ai=AIConfig(provider='anthropic', model='claude-sonnet-4-20250514'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        self.provider = UnifiedAIProvider(self.cfg)

        # Build a fake anthropic module
        class FakeToolUse:
            def __init__(self, payload):
                self.type = 'tool_use'
                self.name = 'commit_organizer'
                self.input = payload

        class FakeMessages:
            def __init__(self, response):
                self._response = response
            def create(self, **kwargs):
                return self._response

        class FakeClient:
            def __init__(self):
                # Content has a tool_use element matching the schema
                payload = {"commits": [{"message": "feat: x", "hunk_ids": [], "rationale": "r"}]}
                self.messages = FakeMessages(types.SimpleNamespace(content=[FakeToolUse(payload)]))

        class FakeAnthropic(types.SimpleNamespace):
            def __init__(self):
                super().__init__(Anthropic=lambda api_key=None: FakeClient())

        # Inject stub module and env var
        self.prev = sys.modules.get('anthropic')
        sys.modules['anthropic'] = FakeAnthropic()
        os.environ['ANTHROPIC_API_KEY'] = 'fake'

    def tearDown(self):
        if self.prev is None:
            sys.modules.pop('anthropic', None)
        else:
            sys.modules['anthropic'] = self.prev

    def test_anthropic_structured_output(self):
        out = self.provider._generate_anthropic('hello world')
        parsed = json.loads(out)
        self.assertIn('commits', parsed)
        self.assertIsInstance(parsed['commits'], list)


class TestGeminiStubbed(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(
            ai=AIConfig(provider='gemini', model='gemini-2.5-pro'),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )
        self.provider = UnifiedAIProvider(self.cfg)

        # Build fake google.generativeai
        class FakeFinishReason:
            def __init__(self, name='OK'):
                self.name = name

        class FakeCandidate:
            def __init__(self, text):
                self.finish_reason = FakeFinishReason('OK')
                # non-empty parts so code path is happy
                self.content = types.SimpleNamespace(parts=['json'])
                self._text = text

        class FakeResponse:
            def __init__(self, text):
                self.candidates = [FakeCandidate(text)]
            @property
            def text(self):
                return self.candidates[0]._text

        class FakeModel:
            def __init__(self, *args, **kwargs):
                pass
            def generate_content(self, prompt, generation_config=None):
                payload = {"commits": [{"message": "feat: y", "hunk_ids": [], "rationale": "r"}]}
                return FakeResponse(json.dumps(payload))

        class FakeGenAI(types.SimpleNamespace):
            def __init__(self):
                super().__init__(configure=lambda api_key=None: None,
                                 GenerativeModel=lambda model_name: FakeModel(),
                                 types=types.SimpleNamespace(GenerationConfig=lambda **kwargs: object()))

        self.prev = sys.modules.get('google.generativeai')
        sys.modules['google.generativeai'] = FakeGenAI()
        os.environ['GEMINI_API_KEY'] = 'fake'

    def tearDown(self):
        if self.prev is None:
            sys.modules.pop('google.generativeai', None)
        else:
            sys.modules['google.generativeai'] = self.prev

    def test_gemini_structured_output(self):
        out = self.provider._generate_gemini('prompt')
        parsed = json.loads(out)
        self.assertIn('commits', parsed)
        self.assertIsInstance(parsed['commits'], list)


if __name__ == '__main__':
    unittest.main()

