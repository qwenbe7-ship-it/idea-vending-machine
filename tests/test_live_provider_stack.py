import unittest
from unittest.mock import patch

import v04_app
from tests.test_evolve_api import IDEA


class _FakeTransport:
    instances = []

    def __init__(self, api_key, timeout_seconds, *, responses_url=None):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.responses_url = responses_url
        self.__class__.instances.append(self)


class _FakeProvider:
    instances = []

    def __init__(self, transport, config):
        self.transport = transport
        self.config = config
        self.__class__.instances.append(self)


class LiveProviderStackTests(unittest.TestCase):
    def setUp(self):
        _FakeTransport.instances = []
        _FakeProvider.instances = []

    def test_groq_is_primary_when_groq_key_is_configured(self):
        captured = {}

        def fake_run_evolution(idea, **kwargs):
            captured["idea"] = idea
            captured.update(kwargs)
            return {"runtime": {"status": "incomplete"}}

        with (
            patch.object(v04_app, "ResponsesTransport", _FakeTransport),
            patch.object(v04_app, "GroqResponsesProvider", _FakeProvider),
            patch.object(v04_app, "run_evolution", fake_run_evolution),
        ):
            runner = v04_app._build_autonomous_runner({"GROQ_API_KEY": "gsk-test"})
            runner(IDEA)

        self.assertEqual(len(_FakeTransport.instances), 3)
        self.assertEqual(len(_FakeProvider.instances), 3)
        self.assertEqual(
            {provider.config.api_key for provider in _FakeProvider.instances},
            {"gsk-test"},
        )
        self.assertEqual(
            {transport.responses_url for transport in _FakeTransport.instances},
            {"https://api.groq.com/openai/v1/responses"},
        )
        self.assertEqual(captured["idea"], IDEA)

    def test_groq_is_preferred_when_both_provider_keys_exist(self):
        with (
            patch.object(v04_app, "ResponsesTransport", _FakeTransport),
            patch.object(v04_app, "GroqResponsesProvider", _FakeProvider),
        ):
            v04_app._build_autonomous_runner(
                {"GROQ_API_KEY": "gsk-test", "OPENAI_API_KEY": "sk-test"}
            )
        self.assertEqual(
            {provider.config.api_key for provider in _FakeProvider.instances},
            {"gsk-test"},
        )

    def test_autonomous_runner_uses_distinct_research_ideation_and_evaluation_providers(self):
        captured = {}

        def fake_run_evolution(idea, **kwargs):
            captured["idea"] = idea
            captured.update(kwargs)
            return {"runtime": {"status": "incomplete"}}

        with (
            patch.object(v04_app, "ResponsesTransport", _FakeTransport),
            patch.object(v04_app, "OpenAIResponsesProvider", _FakeProvider),
            patch.object(v04_app, "run_evolution", fake_run_evolution),
        ):
            runner = v04_app._build_autonomous_runner({"OPENAI_API_KEY": "sk-test"})
            runner(IDEA)

        self.assertEqual(len(_FakeTransport.instances), 3)
        self.assertEqual(len(_FakeProvider.instances), 3)
        research = captured["research_provider"]
        ideation = captured["ideation_provider"]
        evaluation = captured["evaluation_provider"]
        self.assertIsNot(research, ideation)
        self.assertIsNot(research, evaluation)
        self.assertIsNot(ideation, evaluation)
        self.assertEqual(captured["idea"], IDEA)
        self.assertEqual(
            {provider.config.api_key for provider in (research, ideation, evaluation)},
            {"sk-test"},
        )


if __name__ == "__main__":
    unittest.main()
