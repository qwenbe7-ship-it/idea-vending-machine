"""Canonical schema and preflight validation for untrusted Bridge evidence.

This module is the single source of truth for the evidence shape exported to
ChatGPT and the minimum domain checks applied before the existing trusted
Forge/Judge replay machinery runs.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evidence_graph import (
    CONFIDENCE_TIERS,
    EVIDENCE_DIRECTIONS,
    FRESHNESS_STATUSES,
    MARKET_ESTIMATE_KINDS,
    validate_market_size_record,
)

BRIDGE_REF_PATTERN = r"^bc_[A-Za-z0-9_-]{4,64}$"
PUBLICATION_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
_BRIDGE_REF_RE = re.compile(BRIDGE_REF_PATTERN)
_PUBLICATION_DATE_RE = re.compile(PUBLICATION_DATE_PATTERN)

EVIDENCE_DRAFT_KEYS = {
    "bridge_claim_ref",
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
    "candidate_families",
    "notes",
    "raw_excerpt",
    "market_size",
}

CLAIM_REFERENCE_KEYS = {
    "supporting_claim_ids",
    "contradicting_claim_ids",
    "evidence_claim_ids",
}

_EARLY_REFERENCE_SECTIONS = (
    "extract_assumptions",
    "discover_mechanisms",
    "forge_candidates",
)


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _text_array(*, enum: list[str] | None = None, unique: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "string"}
    if enum is not None:
        item["enum"] = enum
    schema: dict[str, Any] = {"type": "array", "items": item}
    if unique:
        schema["uniqueItems"] = True
    return schema


def _market_size_schema() -> dict[str, Any]:
    properties = {
        "base_year": {"type": "integer"},
        "base_value": {"type": "number"},
        "forecast_year": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "forecast_value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "cagr": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "currency": {"type": "string"},
        "unit": {"type": "string"},
        "geography": {"type": "string"},
        "market_definition": {"type": "string"},
        "estimate_kind": {"type": "string", "enum": sorted(MARKET_ESTIMATE_KINDS)},
        "source_definition_note": {"type": "string"},
    }
    return _object_schema(properties)


def evidence_draft_schema() -> dict[str, Any]:
    """Return the exact ChatGPT-facing schema for one untrusted evidence draft."""
    properties = {
        "bridge_claim_ref": {"type": "string", "pattern": BRIDGE_REF_PATTERN},
        "claim": {"type": "string"},
        "source_title": {"type": "string"},
        "source_url": {"type": "string", "pattern": r"^https?://"},
        "publisher": {"type": "string"},
        "publication_date": {"type": "string", "pattern": PUBLICATION_DATE_PATTERN},
        "geography": {"type": "string"},
        "population_or_market_definition": {"type": "string"},
        "evidence_type": {"type": "string"},
        "supports_or_contradicts": {"type": "string", "enum": sorted(EVIDENCE_DIRECTIONS)},
        "confidence_tier": {"type": "string", "enum": sorted(CONFIDENCE_TIERS)},
        "freshness_status": {"type": "string", "enum": sorted(FRESHNESS_STATUSES)},
        "candidate_families": _text_array(enum=sorted(CANDIDATE_FAMILIES), unique=True),
        "notes": {"type": "string"},
        "raw_excerpt": {"type": "string"},
        "market_size": {"anyOf": [{"type": "null"}, _market_size_schema()]},
    }
    return _object_schema(properties)


def _require_non_empty_text(value: Any, code: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(code)


def _validate_http_url(value: Any) -> None:
    _require_non_empty_text(value, "bridge_source_url_invalid")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("bridge_source_url_invalid")


def _validate_publication_date(value: Any) -> None:
    if not isinstance(value, str) or not _PUBLICATION_DATE_RE.fullmatch(value):
        raise ValueError("bridge_publication_date_invalid")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("bridge_publication_date_invalid") from exc


def validate_bridge_evidence_draft(draft: Any) -> None:
    """Validate one untrusted evidence draft without creating trusted IDs."""
    if not isinstance(draft, dict) or set(draft) != EVIDENCE_DRAFT_KEYS:
        raise ValueError("bridge_evidence_draft_invalid")

    ref = draft["bridge_claim_ref"]
    if not isinstance(ref, str) or not _BRIDGE_REF_RE.fullmatch(ref):
        raise ValueError("bridge_claim_ref_invalid")

    for field in (
        "claim",
        "source_title",
        "publisher",
        "geography",
        "population_or_market_definition",
        "evidence_type",
    ):
        _require_non_empty_text(draft[field], f"bridge_{field}_invalid")

    _validate_http_url(draft["source_url"])
    _validate_publication_date(draft["publication_date"])

    if draft["supports_or_contradicts"] not in EVIDENCE_DIRECTIONS:
        raise ValueError("bridge_evidence_direction_invalid")
    if draft["confidence_tier"] not in CONFIDENCE_TIERS:
        raise ValueError("bridge_confidence_tier_invalid")
    if draft["freshness_status"] not in FRESHNESS_STATUSES:
        raise ValueError("bridge_freshness_status_invalid")

    families = draft["candidate_families"]
    if not isinstance(families, list) or any(not isinstance(item, str) for item in families):
        raise ValueError("bridge_candidate_families_invalid")
    if len(families) != len(set(families)):
        raise ValueError("bridge_candidate_families_duplicate")
    if not set(families).issubset(CANDIDATE_FAMILIES):
        raise ValueError("bridge_candidate_family_unknown")

    if not isinstance(draft["notes"], str) or not isinstance(draft["raw_excerpt"], str):
        raise ValueError("bridge_evidence_text_invalid")

    market_size = draft["market_size"]
    if market_size is not None:
        try:
            validate_market_size_record(market_size)
        except ValueError as exc:
            raise ValueError("bridge_market_size_invalid") from exc


def _walk_claim_references(value: Any, allowed_claim_refs: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _walk_claim_references(item, allowed_claim_refs)
        return
    if not isinstance(value, dict):
        return

    for key, item in value.items():
        if key in CLAIM_REFERENCE_KEYS:
            if not isinstance(item, list):
                raise ValueError("bridge_claim_reference_list_invalid")
            for ref in item:
                if not isinstance(ref, str) or not _BRIDGE_REF_RE.fullmatch(ref):
                    raise ValueError("bridge_claim_reference_invalid")
                if ref not in allowed_claim_refs:
                    raise ValueError("bridge_claim_reference_unknown")
        else:
            _walk_claim_references(item, allowed_claim_refs)


def validate_forge_bridge_result(result: Any) -> None:
    """Preflight phase-order-sensitive Bridge rules before trusted replay.

    The existing Forge runtime still performs all of its deterministic gates.
    This preflight exists so exported rules and server rejection behavior cannot
    silently drift or collapse into a later generic provider/runtime error.
    """
    if not isinstance(result, dict):
        raise ValueError("bridge_forge_result_invalid")

    landscape = result.get("landscape_research")
    collision = result.get("collision_research")
    if not isinstance(landscape, list) or not landscape:
        raise ValueError("bridge_landscape_research_invalid")
    if not isinstance(collision, list) or not collision:
        raise ValueError("bridge_collision_research_invalid")

    landscape_refs: set[str] = set()
    all_refs: set[str] = set()
    for draft in landscape:
        validate_bridge_evidence_draft(draft)
        if draft["candidate_families"]:
            raise ValueError("bridge_landscape_candidate_families_invalid")
        ref = draft["bridge_claim_ref"]
        if ref in all_refs:
            raise ValueError("bridge_claim_ref_duplicate")
        all_refs.add(ref)
        landscape_refs.add(ref)

    for section in _EARLY_REFERENCE_SECTIONS:
        value = result.get(section)
        if not isinstance(value, dict):
            raise ValueError("bridge_ideation_result_missing")
        _walk_claim_references(value, landscape_refs)

    for draft in collision:
        validate_bridge_evidence_draft(draft)
        ref = draft["bridge_claim_ref"]
        if ref in all_refs:
            raise ValueError("bridge_claim_ref_duplicate")
        all_refs.add(ref)
