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
MARKET_ESTIMATE_KINDS = {"reported", "derived", "scenario"}

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

MARKET_SIZE_KEYS = {
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


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_market_size_record(market_size: dict[str, Any]) -> None:
    """Validate one market-size estimate without inventing cross-report precision."""
    if not isinstance(market_size, dict) or set(market_size) != MARKET_SIZE_KEYS:
        raise ValueError("market_size keys do not match the v0.3 contract")

    for field in ("currency", "unit", "geography", "market_definition"):
        _require_non_empty_text(field, market_size[field])
    if not isinstance(market_size["source_definition_note"], str):
        raise ValueError("source_definition_note must be a string")

    base_year = market_size["base_year"]
    if not isinstance(base_year, int) or isinstance(base_year, bool) or base_year < 1900:
        raise ValueError("base_year must be a valid integer year")
    if not _is_number(market_size["base_value"]) or market_size["base_value"] < 0:
        raise ValueError("base_value must be a non-negative number")

    forecast_year = market_size["forecast_year"]
    forecast_value = market_size["forecast_value"]
    if (forecast_year is None) != (forecast_value is None):
        if forecast_year is None:
            raise ValueError("forecast_year is required when forecast_value is present")
        raise ValueError("forecast_value is required when forecast_year is present")
    if forecast_year is not None:
        if not isinstance(forecast_year, int) or isinstance(forecast_year, bool):
            raise ValueError("forecast_year must be an integer or null")
        if forecast_year <= base_year:
            raise ValueError("forecast_year must be later than base_year")
        if not _is_number(forecast_value) or forecast_value < 0:
            raise ValueError("forecast_value must be a non-negative number")

    cagr = market_size["cagr"]
    if cagr is not None and not _is_number(cagr):
        raise ValueError("cagr must be a number or null")

    if market_size["estimate_kind"] not in MARKET_ESTIMATE_KINDS:
        raise ValueError(f"estimate_kind must be one of {sorted(MARKET_ESTIMATE_KINDS)}")


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
    if record["market_size"] is not None:
        validate_market_size_record(record["market_size"])


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


def audit_evidence_coverage(
    graph: dict[str, Any], material_claim_ids: list[str] | None = None
) -> dict[str, Any]:
    """Summarize evidence balance and whether it is safe for later decision logic."""
    if not isinstance(graph, dict) or set(graph) != {"evolution_id", "records"}:
        raise ValueError("graph does not match the evidence graph contract")
    records = graph["records"]
    if not isinstance(records, list):
        raise ValueError("graph records must be a list")
    for record in records:
        validate_evidence_record(record)

    material_claim_ids = material_claim_ids or []
    if not isinstance(material_claim_ids, list) or not all(
        isinstance(claim_id, str) and claim_id.strip() for claim_id in material_claim_ids
    ):
        raise ValueError("material_claim_ids must be a list of non-empty strings")

    present_claim_ids = {record["claim_id"] for record in records}
    unresolved = [claim_id for claim_id in material_claim_ids if claim_id not in present_claim_ids]
    support_count = sum(record["supports_or_contradicts"] == "supports" for record in records)
    contradiction_count = sum(
        record["supports_or_contradicts"] == "contradicts" for record in records
    )
    neutral_count = sum(record["supports_or_contradicts"] == "neutral" for record in records)
    stale_count = sum(record["freshness_status"] in {"stale", "historical"} for record in records)
    confidence_distribution = {
        tier: sum(record["confidence_tier"] == tier for record in records)
        for tier in sorted(CONFIDENCE_TIERS)
    }
    high_quality_count = confidence_distribution["A"] + confidence_distribution["B"]

    decision_ready = (
        bool(records)
        and support_count > 0
        and contradiction_count > 0
        and not unresolved
        and high_quality_count > 0
    )

    return {
        "record_count": len(records),
        "support_count": support_count,
        "contradiction_count": contradiction_count,
        "neutral_count": neutral_count,
        "stale_count": stale_count,
        "confidence_distribution": confidence_distribution,
        "unresolved_material_claims": unresolved,
        "decision_ready": decision_ready,
    }


def compare_market_estimates(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare market estimates while refusing to average incompatible definitions."""
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty list")

    estimates = []
    signatures = set()
    for record in records:
        validate_evidence_record(record)
        market_size = record["market_size"]
        if market_size is None:
            raise ValueError("all records must contain market_size data")
        validate_market_size_record(market_size)
        signature = (
            market_size["market_definition"].strip().casefold(),
            market_size["geography"].strip().casefold(),
            market_size["currency"].strip().casefold(),
            market_size["unit"].strip().casefold(),
            market_size["base_year"],
        )
        signatures.add(signature)
        estimates.append(
            {
                "evidence_id": record["evidence_id"],
                "publisher": record["publisher"],
                "market_definition": market_size["market_definition"],
                "geography": market_size["geography"],
                "base_year": market_size["base_year"],
                "base_value": market_size["base_value"],
                "forecast_year": market_size["forecast_year"],
                "forecast_value": market_size["forecast_value"],
                "estimate_kind": market_size["estimate_kind"],
            }
        )

    definitions = sorted({estimate["market_definition"] for estimate in estimates})
    compatible = len(signatures) == 1
    if not compatible:
        return {
            "compatible": False,
            "mode": "definition_range",
            "definitions": definitions,
            "estimates": estimates,
            "reason": "Market definitions, geography, units, currency, or base years differ; averaging is prohibited.",
        }

    base_values = [estimate["base_value"] for estimate in estimates]
    return {
        "compatible": True,
        "mode": "comparable_range",
        "definitions": definitions,
        "estimates": estimates,
        "min_base_value": min(base_values),
        "max_base_value": max(base_values),
    }
