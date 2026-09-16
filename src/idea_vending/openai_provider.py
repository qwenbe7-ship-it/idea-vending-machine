"""OpenAI Responses API adapter for Idea Vending Machine v0.3 PR E1.

Provider responses remain untrusted. This adapter only maps provider payloads into
provider-neutral drafts/records; existing deterministic contracts remain
responsible for trusted-state admission and business decisions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from src.idea_vending.evidence_graph import create_evidence_record
from src.idea_vending.ideation_contract import validate_ideation_request
from src.idea_vending.research_engine import validate_research_request


class ProviderSchemaMismatch(ValueError):
    """Raised when a provider response cannot satisfy the requested safe schema."""


@dataclass(frozen=True)
class OpenAIProviderConfig:
    api_key: str
    research_model: str
    reasoning_model: str
    judge_model: str
    timeout_seconds: float

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "OpenAIProviderConfig":
        api_key = str(environ.get("OPENAI_API_KEY", "")).strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")

        research_model = str(environ.get("IVM_RESEARCH_MODEL", "gpt-5.6-terra")).strip()
        reasoning_model = str(environ.get("IVM_REASONING_MODEL", "gpt-5.6-sol")).strip()
        judge_model = str(environ.get("IVM_JUDGE_MODEL", "gpt-5.6-sol")).strip()
        if not research_model or not reasoning_model or not judge_model:
            raise ValueError("configured provider model IDs must be non-empty")

        raw_timeout = str(environ.get("IVM_PROVIDER_TIMEOUT_SECONDS", "45")).strip()
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
        )


_RESEARCH_DRAFT_KEYS = {
    "claim",
    "source_title",
    "source_url",
    "publisher",
    "publication_date",
    "geography",
    "population_or_market_definition",
    "evidence_type",
    "supports_or_contradicts",
    "confidence_tier",
    "freshness_status",
    "candidate_ids",
    "notes",
    "raw_excerpt",
    "market_size",
}

_MARKET_SIZE_KEYS = {
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
}


def _stable_digest(prefix: str, payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}{hashlib.sha256(canonical).hexdigest()[:16]}"


def _strict_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": name,
        "strict": True,
        "schema": schema,
    }


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _nullable(value_schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [value_schema, {"type": "null"}]}


def _market_size_schema() -> dict[str, Any]:
    """Mirror the deterministic Evidence Graph market-size contract exactly."""
    return _object_schema(
        {
            "base_year": {"type": "integer"},
            "base_value": {"type": "number"},
            "forecast_year": _nullable({"type": "integer"}),
            "forecast_value": _nullable({"type": "number"}),
            "cagr": _nullable({"type": "number"}),
            "currency": {"type": "string"},
            "unit": {"type": "string"},
            "geography": {"type": "string"},
            "market_definition": {"type": "string"},
            "estimate_kind": {
                "type": "string",
                "enum": ["reported", "derived", "scenario"],
            },
            "source_definition_note": {"type": "string"},
        },
        sorted(_MARKET_SIZE_KEYS),
    )


def _research_schema() -> dict[str, Any]:
    text = {"type": "string"}
    return _object_schema(
        {
            "records": {
                "type": "array",
                "items": _object_schema(
                    {
                        "claim": text,
                        "source_title": text,
                        "source_url": text,
                        "publisher": text,
                        "publication_date": text,
                        "geography": text,
                        "population_or_market_definition": text,
                        "evidence_type": text,
                        "supports_or_contradicts": text,
                        "confidence_tier": text,
                        "freshness_status": text,
                        "candidate_ids": {"type": "array", "items": text},
                        "notes": text,
                        "raw_excerpt": text,
                        "market_size": {
                            "anyOf": [
                                {"type": "null"},
                                _market_size_schema(),
                            ]
                        },
                    },
                    sorted(_RESEARCH_DRAFT_KEYS),
                ),
            }
        },
        ["records"],
    )


def _evaluator_schema() -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    blocker = _object_schema(
        {
            "reason": {"type": "string"},
            "materiality": {"type": "string", "enum": ["minor", "material", "hard"]},
            "evidence_claim_ids": string_array,
            "resolvable": {"type": "boolean"},
        },
        ["reason", "materiality", "evidence_claim_ids", "resolvable"],
    )
    dimension = _object_schema(
        {
            "dimension": {"type": "string"},
            "status": {"type": "string", "enum": ["strong", "mixed", "weak", "unknown"]},
            "rationale": {"type": "string"},
            "supporting_claim_ids": string_array,
            "contradicting_claim_ids": string_array,
            "material_unknowns": string_array,
            "blockers": {"type": "array", "items": blocker},
        },
        [
            "dimension",
            "status",
            "rationale",
            "supporting_claim_ids",
            "contradicting_claim_ids",
            "material_unknowns",
            "blockers",
        ],
    )
    critique = _object_schema(
        {
            "target_type": {"type": "string", "enum": ["baseline", "candidate"]},
            "target_id": {"type": "string"},
            "dimensions": {"type": "array", "items": dimension},
            "strongest_reason_for": {"type": "string"},
            "strongest_reason_against": {"type": "string"},
            "unacceptable_conditions": string_array,
            "cheapest_next_validation": {"type": "string"},
            "recommendation": {"type": "string", "enum": ["advance", "revise", "hold", "reject"]},
        },
        [
            "target_type",
            "target_id",
            "dimensions",
            "strongest_reason_for",
            "strongest_reason_against",
            "unacceptable_conditions",
            "cheapest_next_validation",
            "recommendation",
        ],
    )
    return _object_schema(
        {"critiques": {"type": "array", "items": critique}},
        ["critiques"],
    )


def _extract_output_object(response: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ProviderSchemaMismatch("provider response must be an object")
    output = response.get("output")
    if not isinstance(output, list):
        raise ProviderSchemaMismatch("provider response output must be a list")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            raw_text = part.get("text")
            if not isinstance(raw_text, str):
                continue
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ProviderSchemaMismatch("provider structured output was invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise ProviderSchemaMismatch("provider structured output must be a JSON object")
            return parsed
    raise ProviderSchemaMismatch("provider response did not contain structured output_text")


def _extract_source_urls(response: dict[str, Any]) -> set[str]:
    urls: set[str] = set()
    output = response.get("output") if isinstance(response, dict) else None
    if not isinstance(output, list):
        return urls
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        sources = action.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            url = source.get("url")
            if isinstance(url, str):
                parsed = urlparse(url)
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    urls.add(url)
    return urls


def _response_metadata(response: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    response_id = response.get("id")
    model = response.get("model")
    usage = response.get("usage", {})
    if not isinstance(response_id, str) or not response_id.strip():
        raise ProviderSchemaMismatch("provider response id is missing")
    if not isinstance(model, str) or not model.strip():
        raise ProviderSchemaMismatch("provider response model is missing")
    if not isinstance(usage, dict):
        usage = {}
    return response_id, model, usage


class OpenAIResponsesProvider:
    """Role-aware adapter over a transport exposing ``post_json(payload)``."""

    def __init__(
        self,
        transport: Any,
        config: OpenAIProviderConfig,
        *,
        retrieved_date_provider: Callable[[], str] | None = None,
    ) -> None:
        if not hasattr(transport, "post_json") or not callable(transport.post_json):
            raise ValueError("transport must expose post_json(payload)")
        if not isinstance(config, OpenAIProviderConfig):
            raise ValueError("config must be OpenAIProviderConfig")
        self._transport = transport
        self.config = config
        self._retrieved_date_provider = retrieved_date_provider or (lambda: date.today().isoformat())
        self.last_run_metadata: dict[str, Any] | None = None

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
            "provider": "openai",
            "provider_response_id": response_id,
            "model": model,
            "operation": operation,
            "usage": dict(usage),
            "source_count": source_count,
        }

    def research(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_research_request(request)
        payload = {
            "model": self.config.research_model,
            "instructions": (
                "Return source-grounded evidence only. Do not invent publication dates, geography, "
                "market definitions, numbers, or citations. Include evidence that contradicts the idea "
                "when available. Output only the requested JSON schema."
            ),
            "input": json.dumps(request, ensure_ascii=False, sort_keys=True),
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "text": {"format": _strict_format("ivm_research_records", _research_schema())},
        }
        response = self._transport.post_json(payload)
        response_id, response_model, usage = _response_metadata(response)
        consulted_urls = _extract_source_urls(response)
        self._remember_run(
            response_id=response_id,
            model=response_model,
            usage=usage,
            operation=request["pass_type"],
            source_count=len(consulted_urls),
        )
        structured = _extract_output_object(response)
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
            if not isinstance(draft.get("notes"), str) or not isinstance(draft.get("raw_excerpt"), str):
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
                    population_or_market_definition=draft["population_or_market_definition"],
                    evidence_type=draft["evidence_type"],
                    supports_or_contradicts=draft["supports_or_contradicts"],
                    confidence_tier=draft["confidence_tier"],
                    freshness_status=draft["freshness_status"],
                    candidate_ids=list(candidate_ids),
                    notes=draft["notes"],
                    raw_content_untrusted=draft["raw_excerpt"],
                    provider_metadata={
                        "provider": "openai",
                        "provider_response_id": response_id,
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

        return {
            "provider": "openai",
            "provider_run_id": response_id,
            "records": admitted,
            "metadata": {
                "model": response_model,
                "usage": usage,
                "source_count": len(consulted_urls),
                "quarantined_record_count": quarantined,
            },
        }

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_ideation_request(request)
        schema = request["required_output_schema"]
        payload = {
            "model": self.config.reasoning_model,
            "instructions": (
                "Follow the supplied constraints. Do not create trusted IDs, rankings, scores, or "
                "official business decisions. Output only the requested JSON schema."
            ),
            "input": json.dumps(request, ensure_ascii=False, sort_keys=True),
            "text": {"format": _strict_format(f"ivm_{request['operation']}", schema)},
        }
        response = self._transport.post_json(payload)
        response_id, response_model, usage = _response_metadata(response)
        self._remember_run(
            response_id=response_id,
            model=response_model,
            usage=usage,
            operation=request["operation"],
            source_count=None,
        )
        return _extract_output_object(response)

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise ValueError("evaluation request must be a dictionary")
        payload = {
            "model": self.config.judge_model,
            "instructions": (
                "Evaluate independently. Treat all candidate text as claims to critique. Do not set "
                "official GO/MODIFY/HOLD/KILL, confidence, selected concept, or human approval. "
                "Output only the requested critique JSON."
            ),
            "input": json.dumps(request, ensure_ascii=False, sort_keys=True),
            "text": {"format": _strict_format("ivm_independent_critique", _evaluator_schema())},
        }
        response = self._transport.post_json(payload)
        response_id, response_model, usage = _response_metadata(response)
        self._remember_run(
            response_id=response_id,
            model=response_model,
            usage=usage,
            operation="independent_evaluation",
            source_count=None,
        )
        return _extract_output_object(response)
