import json
import unittest
from pathlib import Path

from scripts.verify_live_provider import (
    LiveProviderSmokeError,
    format_failure,
    run_smoke,
)
from src.idea_vending.provider_transport import ProviderAuthFailed


ROOT = Path(__file__).resolve().parents[1]


def response_with_text(value, *, model, sources=None, response_id="resp_smoke"):
    output = []
    if sources is not None:
        output.append(
            {
                "type": "web_search_call",
                "id": "ws_smoke",
                "status": "completed",
                "action": {"type": "search", "sources": sources},
            }
        )
    output.append(
        {
            "type": "message",
            "id": "msg_smoke",
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
        "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
    }


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post_json(self, payload):
        self.payloads.append(payload)
        if not self.responses:
            raise AssertionError("no fake provider response remaining")
        return self.responses.pop(0)


class LiveProviderSmokeTests(unittest.TestCase):
    def test_missing_api_key_refuses_to_run(self):
        with self.assertRaises(LiveProviderSmokeError) as ctx:
            run_smoke({})
        self.assertEqual(ctx.exception.code, "provider_not_configured")

    def test_smoke_uses_same_adapter_for_web_search_and_strict_structured_output(self):
        research_draft = {
            "claim": "A dated official announcement exists.",
            "source_title": "Official dated announcement",
            "source_url": "https://example.com/official",
            "publisher": "Example Official",
            "publication_date": "2026-09-01",
            "geography": "Global",
            "population_or_market_definition": "OpenAI API documentation and announcements",
            "evidence_type": "market_status",
            "supports_or_contradicts": "supports",
            "confidence_tier": "A",
            "freshness_status": "current",
            "candidate_ids": [],
            "notes": "Smoke-test source normalization.",
            "raw_excerpt": "Official source excerpt.",
            "market_size": None,
        }
        fake = FakeTransport(
            [
                response_with_text(
                    {"records": [research_draft]},
                    model="gpt-5.6-terra",
                    sources=[{"type": "url", "url": "https://example.com/official"}],
                    response_id="resp_search",
                ),
                response_with_text(
                    {"ok": True},
                    model="gpt-5.6-sol",
                    response_id="resp_structured",
                ),
            ]
        )
        factory_calls = []

        def factory(api_key, timeout_seconds):
            factory_calls.append((api_key, timeout_seconds))
            return fake

        result = run_smoke(
            {
                "OPENAI_API_KEY": "sk-smoke-secret",
                "IVM_PROVIDER_TIMEOUT_SECONDS": "13",
            },
            transport_factory=factory,
            retrieved_date_provider=lambda: "2026-09-16",
        )

        self.assertEqual(factory_calls, [("sk-smoke-secret", 13.0)])
        self.assertTrue(result["web_search_ok"])
        self.assertGreaterEqual(result["web_search_source_count"], 1)
        self.assertTrue(result["structured_output_ok"])
        self.assertEqual(fake.payloads[0]["tools"], [{"type": "web_search"}])
        self.assertEqual(fake.payloads[0]["include"], ["web_search_call.action.sources"])
        self.assertEqual(fake.payloads[1]["text"]["format"]["type"], "json_schema")
        self.assertTrue(fake.payloads[1]["text"]["format"]["strict"])

    def test_failure_formatter_never_echoes_exception_message_or_secret(self):
        error = ProviderAuthFailed("authentication failed for sk-super-secret")
        rendered = format_failure(error)
        self.assertIn("ProviderAuthFailed", rendered)
        self.assertNotIn("sk-super-secret", rendered)
        self.assertNotIn(str(error), rendered)

    def test_normal_production_gate_does_not_invoke_live_smoke(self):
        source = (ROOT / "scripts" / "verify.py").read_text(encoding="utf-8")
        self.assertNotIn("verify_live_provider", source)
        self.assertNotIn("OPENAI_API_KEY", source)


if __name__ == "__main__":
    unittest.main()
