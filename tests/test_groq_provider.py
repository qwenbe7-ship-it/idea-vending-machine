import copy
import json
import unittest

from src.idea_vending.evidence_graph import validate_evidence_record
from src.idea_vending.groq_provider import (
    GROQ_RESPONSES_URL,
    GroqProviderConfig,
    GroqResponsesProvider,
)
from src.idea_vending.openai_provider import ProviderSchemaMismatch


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post_json(self, payload):
        self.payloads.append(copy.deepcopy(payload))
        if not self.responses:
            raise AssertionError("no fake Groq response available")
        return copy.deepcopy(self.responses.pop(0))


def response_with_text(text, *, model="openai/gpt-oss-120b", response_id="resp_groq_1"):
    return {
        "id": response_id,
        "model": model,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
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
        "research_id": "research_groq01",
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


class GroqProviderConfigTests(unittest.TestCase):
    def test_defaults_to_gpt_oss_120b_and_requires_groq_key(self):
        config = GroqProviderConfig.from_environ({"GROQ_API_KEY": "gsk-test"})
        self.assertEqual(config.research_model, "openai/gpt-oss-120b")
        self.assertEqual(config.reasoning_model, "openai/gpt-oss-120b")
        self.assertEqual(config.judge_model, "openai/gpt-oss-120b")
        self.assertEqual(config.responses_url, GROQ_RESPONSES_URL)

        with self.assertRaisesRegex(ValueError, "GROQ_API_KEY"):
            GroqProviderConfig.from_environ({})


class GroqResponsesProviderTests(unittest.TestCase):
    def make_config(self):
        return GroqProviderConfig.from_environ({"GROQ_API_KEY": "gsk-test"})

    def test_supports_intent_planning(self):
        self.assertTrue(GroqResponsesProvider.supports_intent_planning)

    def test_research_splits_browser_search_from_strict_normalization(self):
        search_text = (
            "Source dossier. Exact URL: https://example.com/report "
            "Published 2026-08-01. The market has entered an early-scale phase."
        )
        normalized = json.dumps({"records": [valid_research_draft()]}, ensure_ascii=False)
        fake = FakeTransport(
            [
                response_with_text(search_text, response_id="resp_search"),
                response_with_text(normalized, response_id="resp_normalize"),
            ]
        )
        provider = GroqResponsesProvider(
            fake,
            self.make_config(),
            retrieved_date_provider=lambda: "2026-09-18",
        )

        result = provider.research(landscape_request())

        self.assertEqual(len(fake.payloads), 2)
        search_payload, normalize_payload = fake.payloads

        self.assertEqual(search_payload["model"], "openai/gpt-oss-120b")
        self.assertEqual(search_payload["tools"], [{"type": "browser_search"}])
        self.assertEqual(search_payload["tool_choice"], "required")
        self.assertNotIn("text", search_payload)
        self.assertEqual(search_payload["reasoning"]["effort"], "low")

        self.assertEqual(normalize_payload["model"], "openai/gpt-oss-120b")
        self.assertNotIn("tools", normalize_payload)
        self.assertEqual(normalize_payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(normalize_payload["text"]["format"]["strict"])
        self.assertEqual(normalize_payload["reasoning"]["effort"], "high")
        self.assertIn("https://example.com/report", normalize_payload["input"])

        self.assertEqual(result["provider"], "groq")
        self.assertEqual(result["provider_run_id"], "resp_normalize")
        self.assertEqual(result["metadata"]["search_response_id"], "resp_search")
        self.assertEqual(result["metadata"]["source_count"], 1)
        self.assertEqual(len(result["records"]), 1)
        record = result["records"][0]
        validate_evidence_record(record)
        self.assertEqual(record["provider_metadata"]["provider"], "groq")

    def test_research_rejects_normalized_url_not_seen_in_browser_transcript(self):
        search_text = "Only consulted https://example.com/report on 2026-08-01."
        normalized = json.dumps(
            {"records": [valid_research_draft(source_url="https://other.example/report")]},
            ensure_ascii=False,
        )
        provider = GroqResponsesProvider(
            FakeTransport(
                [
                    response_with_text(search_text, response_id="resp_search"),
                    response_with_text(normalized, response_id="resp_normalize"),
                ]
            ),
            self.make_config(),
            retrieved_date_provider=lambda: "2026-09-18",
        )

        with self.assertRaises(ProviderSchemaMismatch):
            provider.research(landscape_request())

    def test_generate_and_evaluate_use_strict_gpt_oss_schema(self):
        generate_result = {"assumptions": [{"statement": "x"}]}
        evaluate_result = {"critiques": []}
        fake = FakeTransport(
            [
                response_with_text(json.dumps(generate_result), response_id="resp_generate"),
                response_with_text(json.dumps(evaluate_result), response_id="resp_eval"),
            ]
        )
        provider = GroqResponsesProvider(fake, self.make_config())
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

        self.assertEqual(provider.generate(request), generate_result)
        self.assertEqual(
            provider.evaluate(
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
            ),
            evaluate_result,
        )

        for payload in fake.payloads:
            self.assertEqual(payload["model"], "openai/gpt-oss-120b")
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertTrue(payload["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
