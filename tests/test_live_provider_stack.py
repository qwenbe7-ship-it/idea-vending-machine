import unittest
from unittest.mock import patch

import v04_app
from tests.test_evolve_api import IDEA


class _FakeTransport:
    instances = []

    def __init__(self, api_key, timeout_seconds):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
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
