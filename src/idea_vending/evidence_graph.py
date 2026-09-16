"""Evidence records and graph validation for Idea Vending Machine v0.3.

All research text is treated as untrusted data. This module only validates and
stores structured evidence; it never executes provider-supplied content.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from typing import Any
from urllib.parse import urlparse

CONFIDENCE_TIERS = {"A", "B", "C", "D"}
EVIDENCE_DIRECTIONS = {"supports", "contradicts", "neutral"}
FRESHNESS_STATUSES = {"current", "aging", "stale", "historical"}

EVIDENCE_RECORD_KEYS = {
    "evidence_id",
    "claim_id",
    "claim",
    "source_title",
    "source_url",
    "publisher",
    "publication_date",
    "retrieved_at",
    "geography",
    "population_or_market_definition",
    "evidence_type",
    "supports_or_contradicts",
    "confidence_tier",
    "freshness_status",
    "candidate_ids",
    "notes",
    "raw_content_untrusted",
    "provider_metadata",
    "market_size",
}

_EVIDENCE_ID_RE = re.compile(r"^ev_[A-Za-z0-9_-]{6,64}$")
_CLAIM_ID_RE = re.compile(r"^claim_[A-Za-z0-9_-]{6,64}$")
_EVOLUTION_ID_RE = re.compile(r"^evo_[A-Za-z0-9_-]{8,64}$")


def _require_non_empty_text(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _validate_iso_date(field: str, value: Any) -> None:
    _require_non_empty_text(field, value)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO calendar date (YYYY-MM-DD)") from exc


def _validate_source_url(value: Any) -> None:
    _require_non_empty_text("source_url", value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must use http or https and include a host")


def validate_evidence_record(record: dict[str, Any]) -> None:
    """Validate one normalized external-evidence record."""
    if not isinstance(record, dict):
        raise ValueError("evidence record must be a dictionary")
    if set(record) != EVIDENCE_RECORD_KEYS:
        raise ValueError("evidence record keys do not match the v0.3 contract")

    evidence_id = record["evidence_id"]
    if not isinstance(evidence_id, str) or not _EVIDENCE_ID_RE.fullmatch(evidence_id):
        raise ValueError("evidence_id must match ev_[A-Za-z0-9_-]{6,64}")

    claim_id = record["claim_id"]
    if not isinstance(claim_id, str) or not _CLAIM_ID_RE.fullmatch(claim_id):
        raise ValueError("claim_id must match claim_[A-Za-z0-9_-]{6,64}")

    for field in (
        "claim",
        "source_title",
        "publisher",
        "geography",
        "population_or_market_definition",
        "evidence_type",
    ):
        _require_non_empty_text(field, record[field])

    _validate_source_url(record["source_url"])
    _validate_iso_date("publication_date", record["publication_date"])
    _validate_iso_date("retrieved_at", record["retrieved_at"])

    if record["supports_or_contradicts"] not in EVIDENCE_DIRECTIONS:
        raise ValueError(
            f"supports_or_contradicts must be one of {sorted(EVIDENCE_DIRECTIONS)}"
        )
    if record["confidence_tier"] not in CONFIDENCE_TIERS:
        raise ValueError(f"confidence_tier must be one of {sorted(CONFIDENCE_TIERS)}")
    if record["freshness_status"] not in FRESHNESS_STATUSES:
        raise ValueError(f"freshness_status must be one of {sorted(FRESHNESS_STATUSES)}")

    candidate_ids = record["candidate_ids"]
    if not isinstance(candidate_ids, list) or not all(
        isinstance(candidate_id, str) and candidate_id.strip() for candidate_id in candidate_ids
    ):
        raise ValueError("candidate_ids must be a list of non-empty strings")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_ids must not contain duplicates")

    if not isinstance(record["notes"], str):
        raise ValueError("notes must be a string")
    if not isinstance(record["raw_content_untrusted"], str):
        raise ValueError("raw_content_untrusted must be a string")
    if not isinstance(record["provider_metadata"], dict):
        raise ValueError("provider_metadata must be a dictionary")
    if record["market_size"] is not None and not isinstance(record["market_size"], dict):
        raise ValueError("market_size must be a dictionary or null")


def create_evidence_record(**fields: Any) -> dict[str, Any]:
    """Return a validated defensive copy of an Evidence Record."""
    record = deepcopy(fields)
    validate_evidence_record(record)
    return record


def create_evidence_graph(evolution_id: str) -> dict[str, Any]:
    """Create an empty evidence graph for one evolution assessment."""
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")
    return {"evolution_id": evolution_id, "records": []}


def add_evidence_record(graph: dict[str, Any], record: dict[str, Any]) -> None:
    """Validate and append evidence while preserving ID uniqueness."""
    if not isinstance(graph, dict) or set(graph) != {"evolution_id", "records"}:
        raise ValueError("graph does not match the evidence graph contract")
    if not isinstance(graph["records"], list):
        raise ValueError("graph records must be a list")

    validate_evidence_record(record)
    for existing in graph["records"]:
        if existing["evidence_id"] == record["evidence_id"]:
            raise ValueError("duplicate evidence_id")
        if existing["claim_id"] == record["claim_id"]:
            raise ValueError("duplicate claim_id")

    graph["records"].append(deepcopy(record))
