"""Groq GPT-OSS provider for autonomous Idea Vending Machine execution.

Groq's GPT-OSS 120B supports Browser Search and strict structured outputs, but
those capabilities cannot be combined in the same request. Research therefore
runs in two explicit stages:

1. Browser Search creates an untrusted, source-grounded dossier.
2. A separate strict JSON-schema call normalizes only that dossier.

All normalized records still pass the existing deterministic Evidence Graph
admission rules. Ideation and Judge reuse the existing strict provider-neutral
schemas while recording Groq as the provider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from src.idea_vending.evidence_graph import create_evidence_record
from src.idea_vending.openai_provider import (
    OpenAIProviderConfig,
    OpenAIResponsesProvider,
    ProviderSchemaMismatch,
    _RESEARCH_DRAFT_KEYS,
    _extract_output_object,
    _research_schema,
    _response_metadata,
    _stable_digest,
    _strict_format,
)
from src.idea_vending.provider_transport import GROQ_RESPONSES_URL
from src.idea_vending.research_engine import validate_research_request
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
_URL_RE = re.compile(r"https?://[^\\s<>{}\\[\\]]+")


@dataclass(frozen=True)
class GroqProviderConfig(OpenAIProviderConfig):
    responses_url: str = GROQ_RESPONSES_URL

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "GroqProviderConfig":
        api_key = str(environ.get("GROQ_API_KEY", "")).strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY is required")

        default_model = str(environ.get("IVM_GROQ_MODEL", DEFAULT_GROQ_MODEL)).strip()
        research_model = str(environ.get("IVM_GROQ_RESEARCH_MODEL", default_model)).strip()
        reasoning_model = str(environ.get("IVM_GROQ_REASONING_MODEL", default_model)).strip()
        judge_model = str(environ.get("IVM_GROQ_JUDGE_MODEL", default_model)).strip()
        if not research_model or not reasoning_model or not judge_model:
            raise ValueError("configured Groq model IDs must be non-empty")

        raw_timeout = str(environ.get("IVM_PROVIDER_TIMEOUT_SECONDS", "60")).strip()
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("IVM_PROVIDER_TIMEOUT_SECONDS must be a positive number") from exc
        if timeout_seconds <= 0:
            raise ValueError("IVM_PROVIDER_TIMEOUT_SECONDS must be a positive number")

        return cls(
            api_key=api_key,
            research_model=research_model,
            reasoning_model=reasoning_model,
            judge_model=judge_model,
            timeout_seconds=timeout_seconds,
            responses_url=GROQ_RESPONSES_URL,
        )


def _extract_output_text(response: dict[str, Any]) -> str:
    if not isinstance(response, dict):
        raise ProviderSchemaMismatch("provider response must be an object")
    output = response.get("output")
    if not isinstance(output, list):
        raise ProviderSchemaMismatch("provider response output must be a list")

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if not chunks:
        raise ProviderSchemaMismatch("provider response did not contain output_text")
    return "\n".join(chunks)


def _urls_from_browser_dossier(text: str) -> set[str]:
    urls: set[str] = set()
    for raw in _URL_RE.findall(text):
        candidate = raw.rstrip(".,;:!?)")
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            urls.add(candidate)
    return urls


class GroqResponsesProvider(OpenAIResponsesProvider):
    """GPT-OSS 120B adapter using Groq Browser Search + strict normalization."""

    supports_intent_planning = True

    def __init__(
        self,
        transport: Any,
        config: GroqProviderConfig,
        *,
        retrieved_date_provider: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(config, GroqProviderConfig):
            raise ValueError("config must be GroqProviderConfig")
        super().__init__(
            transport,
            config,
            retrieved_date_provider=retrieved_date_provider,
        )

    def _remember_run(
        self,
        *,
        response_id: str,
        model: str,
        usage: dict[str, Any],
        operation: str,
        source_count: int | None,
    ) -> None:
        self.last_run_metadata = {
            "provider": "groq",
            "provider_response_id": response_id,
            "model": model,
            "operation": operation,
            "usage": dict(usage),
            "source_count": source_count,
        }

    def research(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_research_request(request)

        search_payload = {
            "model": self.config.research_model,
            "instructions": (
                "Use browser search to build a source-grounded research dossier for the supplied request. "
                "Actively seek counter-evidence, competitors, prior art, failure cases, and implementation blockers. "
                "For every factual source used, print its full absolute http/https URL verbatim in the dossier. "
                "Include the exact publication date only when the source verifies it. Never invent a date, URL, "
                "number, publisher, geography, or market definition. This stage is unstructured research only."
            ),
            "input": json.dumps(request, ensure_ascii=False, sort_keys=True),
            "tools": [{"type": "browser_search"}],
            "tool_choice": "required",
            "reasoning": {"effort": "low"},
        }
        search_response = self._transport.post_json(search_payload)
        search_response_id, search_model, search_usage = _response_metadata(search_response)
        dossier = _extract_output_text(search_response)
        consulted_urls = _urls_from_browser_dossier(dossier)
        if not consulted_urls:
            raise ProviderSchemaMismatch(
                "Groq browser research did not expose any verifiable source URLs"
            )

        normalize_payload = {
            "model": self.config.research_model,
            "instructions": (
                "Normalize only the supplied browser-search dossier into the requested evidence schema. "
                "Do not add facts or sources that are absent from the dossier. source_url must be copied verbatim "
                "from the dossier. Exclude any record whose exact publication date cannot be verified as YYYY-MM-DD. "
                "Preserve counter-evidence. Return only strict JSON matching the schema."
            ),
            "input": json.dumps(
                {
                    "research_request": request,
                    "browser_research_dossier": dossier,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            "reasoning": {"effort": "high"},
            "text": {
                "format": _strict_format(
                    "ivm_groq_research_records",
                    _research_schema(),
                )
            },
        }
        normalize_response = self._transport.post_json(normalize_payload)
        response_id, response_model, usage = _response_metadata(normalize_response)
        structured = _extract_output_object(normalize_response)
        drafts = structured.get("records")
        if not isinstance(drafts, list):
            raise ProviderSchemaMismatch("research structured output must contain records list")

        retrieved_at = self._retrieved_date_provider()
        if not isinstance(retrieved_at, str) or not retrieved_at.strip():
            raise ProviderSchemaMismatch("retrieved date provider returned invalid value")

        admitted: list[dict[str, Any]] = []
        quarantined = 0
        for draft in drafts:
            if not isinstance(draft, dict) or set(draft) != _RESEARCH_DRAFT_KEYS:
                quarantined += 1
                continue
            source_url = draft.get("source_url")
            if not isinstance(source_url, str) or source_url not in consulted_urls:
                quarantined += 1
                continue
            if any(
                not isinstance(draft.get(field), str) or not draft[field].strip()
                for field in (
                    "claim",
                    "source_title",
                    "publisher",
                    "publication_date",
                    "geography",
                    "population_or_market_definition",
                    "evidence_type",
                    "supports_or_contradicts",
                    "confidence_tier",
                    "freshness_status",
                )
            ):
                quarantined += 1
                continue
            candidate_ids = draft.get("candidate_ids")
            if not isinstance(candidate_ids, list) or any(
                not isinstance(candidate_id, str) or not candidate_id.strip()
                for candidate_id in candidate_ids
            ):
                quarantined += 1
                continue
            if not set(candidate_ids).issubset(set(request["candidate_ids"])):
                quarantined += 1
                continue
            if not isinstance(draft.get("notes"), str) or not isinstance(
                draft.get("raw_excerpt"), str
            ):
                quarantined += 1
                continue

            claim_payload = {
                "claim": draft["claim"],
                "source_url": source_url,
                "direction": draft["supports_or_contradicts"],
                "market_definition": draft["population_or_market_definition"],
            }
            claim_id = _stable_digest("claim_", claim_payload)
            evidence_payload = {
                "claim_id": claim_id,
                "source_url": source_url,
                "publication_date": draft["publication_date"],
                "retrieved_at": retrieved_at,
                "response_id": response_id,
            }
            evidence_id = _stable_digest("ev_", evidence_payload)

            try:
                record = create_evidence_record(
                    evidence_id=evidence_id,
                    claim_id=claim_id,
                    claim=draft["claim"],
                    source_title=draft["source_title"],
                    source_url=source_url,
                    publisher=draft["publisher"],
                    publication_date=draft["publication_date"],
                    retrieved_at=retrieved_at,
                    geography=draft["geography"],
                    population_or_market_definition=draft[
                        "population_or_market_definition"
                    ],
                    evidence_type=draft["evidence_type"],
                    supports_or_contradicts=draft["supports_or_contradicts"],
                    confidence_tier=draft["confidence_tier"],
                    freshness_status=draft["freshness_status"],
                    candidate_ids=list(candidate_ids),
                    notes=draft["notes"],
                    raw_content_untrusted=draft["raw_excerpt"],
                    provider_metadata={
                        "provider": "groq",
                        "provider_response_id": response_id,
                        "browser_search_response_id": search_response_id,
                        "model": response_model,
                    },
                    market_size=draft["market_size"],
                )
            except (TypeError, ValueError):
                quarantined += 1
                continue
            admitted.append(record)

        if not admitted:
            raise ProviderSchemaMismatch("provider research returned zero admissible evidence records")

        self._remember_run(
            response_id=response_id,
            model=response_model,
            usage=usage,
            operation=request["pass_type"],
            source_count=len(consulted_urls),
        )
        return {
            "provider": "groq",
            "provider_run_id": response_id,
            "records": admitted,
            "metadata": {
                "model": response_model,
                "usage": usage,
                "search_model": search_model,
                "search_usage": search_usage,
                "search_response_id": search_response_id,
                "source_count": len(consulted_urls),
                "quarantined_record_count": quarantined,
            },
        }
