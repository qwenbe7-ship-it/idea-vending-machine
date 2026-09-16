import json
import unittest

from src.idea_vending.openai_provider import OpenAIProviderConfig, OpenAIResponsesProvider


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post_json(self, payload):
        self.payloads.append(payload)
        return self.responses.pop(0)


def response(value, *, response_id, model, sources=None):
    output = []
    if sources is not None:
        output.append(
            {
                "type": "web_search_call",
                "id": "ws_integrity",
                "status": "completed",
                "action": {"type": "search", "sources": sources},
            }
        )
    output.append(
        {
            "type": "message",
            "id": "msg_integrity",
            "content": [
                {
                    "type": "output_text",
                    "text": json.dumps(value),
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
        "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
    }


def ideation_request():
    return {
        "operation": "extract_assumptions",
        "objective": "Return smoke output",
        "raw_idea": "고객 문의를 자동 분류하는 운영 자동화 시스템",
        "problem_context": {},
        "assumption_context": [],
        "evidence_summary": [],
        "allowed_transformations": [],
        "required_output_schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        "constraints": ["Do not create trusted IDs"],
    }


def research_request():
    return {
        "research_id": "research_integrity01",
        "evolution_id": "evo_integrity01",
        "pass_type": "landscape",
        "question": "What evidence exists?",
        "queries": ["dated authoritative evidence"],
        "required_evidence_categories": ["market_status", "counter_evidence"],
        "candidate_ids": [],
        "status": "pending",
        "evidence_ids": [],
        "provider_runs": [],
    }


def research_draft():
    return {
        "claim": "A source-backed market status claim exists.",
        "source_title": "Dated report",
        "source_url": "https://example.com/report",
        "publisher": "Example Research",
        "publication_date": "2026-09-01",
        "geography": "Global",
        "population_or_market_definition": "Enterprise AI workflow software",
        "evidence_type": "market_status",
        "supports_or_contradicts": "supports",
        "confidence_tier": "A",
        "freshness_status": "current",
        "candidate_ids": [],
        "notes": "Source-backed.",
        "raw_excerpt": "Excerpt.",
        "market_size": None,
    }


class OpenAIProviderIntegrityTests(unittest.TestCase):
    def config(self):
        return OpenAIProviderConfig.from_environ({"OPENAI_API_KEY": "sk-do-not-log"})

    def test_generate_records_sanitized_provider_run_metadata(self):
        fake = FakeTransport([response({"ok": True}, response_id="resp_gen", model="gpt-5.6-sol")])
        provider = OpenAIResponsesProvider(fake, self.config())
        provider.generate(ideation_request())
        self.assertEqual(
            provider.last_run_metadata,
            {
                "provider": "openai",
                "provider_response_id": "resp_gen",
                "model": "gpt-5.6-sol",
                "operation": "extract_assumptions",
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                "source_count": None,
            },
        )
        self.assertNotIn("sk-do-not-log", repr(provider.last_run_metadata))

    def test_evaluate_records_sanitized_provider_run_metadata(self):
        fake = FakeTransport([response({"critiques": []}, response_id="resp_judge", model="gpt-5.6-sol")])
        provider = OpenAIResponsesProvider(fake, self.config())
        provider.evaluate({"evolution_id": "evo_integrity01"})
        self.assertEqual(provider.last_run_metadata["provider_response_id"], "resp_judge")
        self.assertEqual(provider.last_run_metadata["operation"], "independent_evaluation")
        self.assertEqual(provider.last_run_metadata["source_count"], None)
        self.assertNotIn("sk-do-not-log", repr(provider.last_run_metadata))

    def test_research_records_audit_metadata_and_uses_closed_market_size_schema(self):
        fake = FakeTransport(
            [
                response(
                    {"records": [research_draft()]},
                    response_id="resp_research",
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/report"}],
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            fake,
            self.config(),
            retrieved_date_provider=lambda: "2026-09-16",
        )
        provider.research(research_request())
        self.assertEqual(provider.last_run_metadata["provider_response_id"], "resp_research")
        self.assertEqual(provider.last_run_metadata["operation"], "landscape")
        self.assertEqual(provider.last_run_metadata["source_count"], 1)

        schema = fake.payloads[0]["text"]["format"]["schema"]
        market_schema = schema["properties"]["records"]["items"]["properties"]["market_size"]["anyOf"][1]
        self.assertFalse(market_schema["additionalProperties"])
        self.assertEqual(
            set(market_schema["required"]),
            {
                "base_year",
                "base_value",
                "forecast_year",
                "forecast_value",
                "cagr",
                "currency",
                "unit",
                "geography",
                "market_definition",
                "estimate_kind",
                "source_definition_note",
            },
        )


if __name__ == "__main__":
    unittest.main()
