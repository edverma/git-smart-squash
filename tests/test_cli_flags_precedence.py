import unittest

from git_smart_squash.cli import GitSmartSquashCLI
from git_smart_squash.simple_config import Config, AIConfig, HunkConfig, AttributionConfig


class TestCLIFlagPrecedence(unittest.TestCase):
    def setUp(self):
        self.cli = GitSmartSquashCLI()

    def _make_config(self, reasoning='high', max_predict=12345):
        return Config(
            ai=AIConfig(provider='openai', model='gpt-5', reasoning=reasoning, max_predict_tokens=max_predict),
            hunks=HunkConfig(),
            attribution=AttributionConfig(),
            auto_apply=False,
        )

    def test_defaults_do_not_override_config(self):
        parser = self.cli.create_parser()
        args = parser.parse_args([])

        cfg = self._make_config(reasoning='high', max_predict=12345)

        # Emulate override logic used in main()
        if args.ai_provider:
            cfg.ai.provider = args.ai_provider
            if not args.model:
                cfg.ai.model = self.cli.config_manager._get_default_model(args.ai_provider)
        if args.model:
            cfg.ai.model = args.model
        if args.reasoning is not None:
            cfg.ai.reasoning = args.reasoning or cfg.ai.reasoning
        if getattr(args, 'max_predict_tokens', None) is not None:
            cfg.ai.max_predict_tokens = args.max_predict_tokens or cfg.ai.max_predict_tokens

        self.assertEqual(cfg.ai.reasoning, 'high')
        self.assertEqual(cfg.ai.max_predict_tokens, 12345)

    def test_flags_override_config_when_provided(self):
        parser = self.cli.create_parser()
        args = parser.parse_args(['--reasoning', 'minimal', '--max-predict-tokens', '777'])

        cfg = self._make_config(reasoning='high', max_predict=12345)

        if args.reasoning is not None:
            cfg.ai.reasoning = args.reasoning or cfg.ai.reasoning
        if getattr(args, 'max_predict_tokens', None) is not None:
            cfg.ai.max_predict_tokens = args.max_predict_tokens or cfg.ai.max_predict_tokens

        self.assertEqual(cfg.ai.reasoning, 'minimal')
        self.assertEqual(cfg.ai.max_predict_tokens, 777)


if __name__ == '__main__':
    unittest.main()

