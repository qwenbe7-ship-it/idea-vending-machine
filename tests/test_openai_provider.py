import copy
import json
import unittest

from src.idea_vending.evidence_graph import validate_evidence_record
from src.idea_vending.openai_provider import (
    OpenAIProviderConfig,
    OpenAIResponsesProvider,
    ProviderSchemaMismatch,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post_json(self, payload):
        self.payloads.append(copy.deepcopy(payload))
        if not self.responses:
            raise AssertionError("no fake provider response available")
        return copy.deepcopy(self.responses.pop(0))


def response_with_text(value, *, model="gpt-5.6-sol", sources=None, response_id="resp_1"):
    output = []
    if sources is not None:
        output.append(
            {
                "type": "web_search_call",
                "id": "ws_1",
                "status": "completed",
                "action": {"type": "search", "sources": sources},
            }
        )
    output.append(
        {
            "type": "message",
            "id": "msg_1",
            "content": [
                {
                    "type": "output_text",
                    "text": json.dumps(value, ensure_ascii=False),
                    "annotations": [],
                }
            ],
        }
    )
    return {
        "id": response_id,
        "model": model,
        "status": "completed",
        "output": output,
        "usage": {"input_tokens": 101, "output_tokens": 55, "total_tokens": 156},
    }


def valid_research_draft(**overrides):
    draft = {
        "claim": "The market has entered an early-scale phase.",
        "source_title": "Market report",
        "source_url": "https://example.com/report",
        "publisher": "Example Research",
        "publication_date": "2026-08-01",
        "geography": "Global",
        "population_or_market_definition": "Enterprise AI workflow software",
        "evidence_type": "market_status",
        "supports_or_contradicts": "supports",
        "confidence_tier": "B",
        "freshness_status": "current",
        "candidate_ids": [],
        "notes": "Methodology disclosed in source.",
        "raw_excerpt": "Enterprise adoption is expanding.",
        "market_size": None,
    }
    draft.update(overrides)
    return draft


def landscape_request():
    return {
        "research_id": "research_live01",
        "evolution_id": "evo_runtime001",
        "pass_type": "landscape",
        "question": "What market evidence supports or contradicts this idea?",
        "queries": ["enterprise AI workflow market evidence"],
        "required_evidence_categories": ["market_status", "counter_evidence"],
        "candidate_ids": [],
        "status": "pending",
        "evidence_ids": [],
        "provider_runs": [],
    }


class OpenAIProviderConfigTests(unittest.TestCase):
    def test_defaults_are_role_specific_and_overridable(self):
        config = OpenAIProviderConfig.from_environ({"OPENAI_API_KEY": "sk-test"})
        self.assertEqual(config.research_model, "gpt-5.6-terra")
        self.assertEqual(config.reasoning_model, "gpt-5.6-sol")
        self.assertEqual(config.judge_model, "gpt-5.6-sol")

        overridden = OpenAIProviderConfig.from_environ(
            {
                "OPENAI_API_KEY": "sk-test",
                "IVM_RESEARCH_MODEL": "research-custom",
                "IVM_REASONING_MODEL": "reasoning-custom",
                "IVM_JUDGE_MODEL": "judge-custom",
                "IVM_PROVIDER_TIMEOUT_SECONDS": "42.5",
            }
        )
        self.assertEqual(overridden.research_model, "research-custom")
        self.assertEqual(overridden.reasoning_model, "reasoning-custom")
        self.assertEqual(overridden.judge_model, "judge-custom")
        self.assertEqual(overridden.timeout_seconds, 42.5)

    def test_missing_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            OpenAIProviderConfig.from_environ({})


class OpenAIResponsesProviderTests(unittest.TestCase):
    def make_config(self):
        return OpenAIProviderConfig.from_environ({"OPENAI_API_KEY": "sk-test"})

    def test_research_uses_web_search_sources_and_strict_json_schema(self):
        fake = FakeTransport(
            [
                response_with_text(
                    {"records": [valid_research_draft()]},
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/report"}],
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            fake,
            self.make_config(),
            retrieved_date_provider=lambda: "2026-09-16",
        )
        result = provider.research(landscape_request())

        payload = fake.payloads[0]
        self.assertEqual(payload["model"], "gpt-5.6-terra")
        self.assertEqual(payload["tools"], [{"type": "web_search"}])
        self.assertEqual(payload["include"], ["web_search_call.action.sources"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])

        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["provider_run_id"], "resp_1")
        self.assertEqual(len(result["records"]), 1)
        record = result["records"][0]
        validate_evidence_record(record)
        self.assertTrue(record["evidence_id"].startswith("ev_"))
        self.assertTrue(record["claim_id"].startswith("claim_"))
        self.assertEqual(record["retrieved_at"], "2026-09-16")
        self.assertEqual(record["provider_metadata"]["provider_response_id"], "resp_1")
        self.assertEqual(result["metadata"]["model"], "gpt-5.6-terra")
        self.assertEqual(result["metadata"]["source_count"], 1)

    def test_research_does_not_fabricate_missing_publication_date(self):
        invalid = valid_research_draft(publication_date="")
        fake = FakeTransport(
            [
                response_with_text(
                    {"records": [valid_research_draft(), invalid]},
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/report"}],
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            fake, self.make_config(), retrieved_date_provider=lambda: "2026-09-16"
        )
        result = provider.research(landscape_request())
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["metadata"]["quarantined_record_count"], 1)

    def test_unconsulted_source_url_is_quarantined(self):
        unconsulted = valid_research_draft(source_url="https://other.example/report")
        fake = FakeTransport(
            [
                response_with_text(
                    {"records": [valid_research_draft(), unconsulted]},
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/report"}],
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            fake, self.make_config(), retrieved_date_provider=lambda: "2026-09-16"
        )
        result = provider.research(landscape_request())
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["metadata"]["quarantined_record_count"], 1)

    def test_zero_admissible_research_records_is_schema_mismatch(self):
        fake = FakeTransport(
            [
                response_with_text(
                    {"records": [valid_research_draft(publication_date="")]},
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/report"}],
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            fake, self.make_config(), retrieved_date_provider=lambda: "2026-09-16"
        )
        with self.assertRaises(ProviderSchemaMismatch):
            provider.research(landscape_request())

    def test_generate_uses_reasoning_model_and_request_schema(self):
        fake = FakeTransport([response_with_text({"assumptions": [{"statement": "x"}]})])
        provider = OpenAIResponsesProvider(fake, self.make_config())
        request = {
            "operation": "extract_assumptions",
            "objective": "Find assumptions",
            "raw_idea": "고객 문의 원인을 예측하는 자동화 시스템",
            "problem_context": {},
            "assumption_context": [],
            "evidence_summary": [],
            "allowed_transformations": [],
            "required_output_schema": {
                "type": "object",
                "properties": {"assumptions": {"type": "array", "items": {"type": "object"}}},
                "required": ["assumptions"],
                "additionalProperties": False,
            },
            "constraints": ["Do not create trusted IDs"],
        }
        result = provider.generate(request)
        payload = fake.payloads[0]
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertEqual(payload["text"]["format"]["schema"], request["required_output_schema"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(result["assumptions"][0]["statement"], "x")

    def test_evaluate_uses_isolated_judge_model_and_returns_only_structured_output(self):
        raw = {"critiques": []}
        fake = FakeTransport([response_with_text(raw, model="gpt-5.6-sol")])
        provider = OpenAIResponsesProvider(fake, self.make_config())
        result = provider.evaluate(
            {
                "evolution_id": "evo_runtime001",
                "baseline": {},
                "candidates": [],
                "evidence_graph": {},
                "candidate_admission_audit": {},
                "feasibility_artifacts": {},
                "collision_state": {},
                "evaluator_policy": {"official_fields_forbidden": True},
            }
        )
        payload = fake.payloads[0]
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(result, raw)

    def test_missing_or_invalid_output_text_is_rejected(self):
        fake = FakeTransport([{"id": "resp_x", "model": "gpt-5.6-sol", "output": [], "usage": {}}])
        provider = OpenAIResponsesProvider(fake, self.make_config())
        with self.assertRaises(ProviderSchemaMismatch):
            provider.generate(
                {
                    "operation": "extract_assumptions",
                    "objective": "x",
                    "raw_idea": "고객 문의를 자동 분류하는 시스템",
                    "problem_context": {},
                    "assumption_context": [],
                    "evidence_summary": [],
                    "allowed_transformations": [],
                    "required_output_schema": {"type": "object", "properties": {}, "additionalProperties": False},
                    "constraints": ["x"],
                }
            )


if __name__ == "__main__":
    unittest.main()
