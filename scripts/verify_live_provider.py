"""Opt-in live OpenAI provider smoke verification for Idea Vending Machine.

This script is deliberately separate from ``scripts/verify.py``. Normal CI never
requires a paid external provider credential. Run manually in the intended
deployment environment when ``OPENAI_API_KEY`` is configured.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, Mapping

from src.idea_vending.ideation_contract import create_ideation_request
from src.idea_vending.openai_provider import OpenAIProviderConfig, OpenAIResponsesProvider
from src.idea_vending.provider_transport import ResponsesTransport
from src.idea_vending.research_engine import create_research_request


class LiveProviderSmokeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def format_failure(exc: BaseException) -> str:
    """Return a sanitized failure label without provider bodies or secret-bearing text."""
    return f"{type(exc).__name__}: live provider smoke failed"


def run_smoke(
    environ: Mapping[str, str],
    *,
    transport_factory: Callable[[str, float], Any] = ResponsesTransport,
    retrieved_date_provider: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Verify one web-search/source path and one strict structured-output path."""
    try:
        config = OpenAIProviderConfig.from_environ(environ)
    except (TypeError, ValueError) as exc:
        raise LiveProviderSmokeError("provider_not_configured") from exc

    transport = transport_factory(config.api_key, config.timeout_seconds)
    provider = OpenAIResponsesProvider(
        transport,
        config,
        retrieved_date_provider=retrieved_date_provider,
    )

    research_request = create_research_request(
        research_id="research_smoke01",
        evolution_id="evo_smoke0001",
        pass_type="landscape",
        question=(
            "Find one recent, explicitly dated, authoritative public source about OpenAI API "
            "capabilities. Return only source-backed metadata; do not infer missing dates."
        ),
        queries=["recent dated official OpenAI API announcement"],
        required_evidence_categories=["market_status", "counter_evidence"],
        candidate_ids=[],
    )
    research_result = provider.research(research_request)
    metadata = research_result.get("metadata", {})
    source_count = metadata.get("source_count") if isinstance(metadata, dict) else None
    if not isinstance(source_count, int) or isinstance(source_count, bool) or source_count < 1:
        raise LiveProviderSmokeError("web_search_sources_missing")
    if not research_result.get("records"):
        raise LiveProviderSmokeError("web_search_evidence_missing")

    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    ideation_request = create_ideation_request(
        operation="extract_assumptions",
        objective="Return exactly {\"ok\": true} as a strict structured-output smoke test.",
        raw_idea="Verify strict structured output for the live provider adapter.",
        problem_context={},
        assumption_context=[],
        evidence_summary=[],
        allowed_transformations=[],
        required_output_schema=schema,
        constraints=["Do not create trusted IDs or official decisions."],
    )
    structured = provider.generate(ideation_request)
    if structured != {"ok": True}:
        raise LiveProviderSmokeError("structured_output_mismatch")

    return {
        "web_search_ok": True,
        "web_search_source_count": source_count,
        "structured_output_ok": True,
        "research_model": config.research_model,
        "reasoning_model": config.reasoning_model,
    }


def main(environ: Mapping[str, str] | None = None) -> int:
    source = os.environ if environ is None else environ
    try:
        result = run_smoke(source)
    except Exception as exc:
        print(f"FAIL: {format_failure(exc)}", file=sys.stderr)
        return 1

    print("Idea Vending Machine Live Provider Smoke")
    print(f"PASS: web search sources ({result['web_search_source_count']})")
    print("PASS: strict structured output")
    print("LIVE PROVIDER GREEN WITH EVIDENCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
