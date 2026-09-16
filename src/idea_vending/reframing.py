"""Deterministic assumption and reframing contracts for Idea Vending Machine v0.3."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

ASSUMPTION_TYPES = {
    "workflow",
    "customer_behavior",
    "business_model",
    "technology",
    "regulation",
    "distribution",
    "data",
    "economics",
}
ASSUMPTION_STATUSES = {"supported", "weak", "contested", "unsupported", "unknown"}
MATERIALITIES = {"none", "minor", "material"}
TRANSFORMATIONS = {
    "AFTER_TO_BEFORE",
    "REPAIR_TO_PREVENT",
    "SEARCH_TO_PREDICT",
    "ADVISE_TO_EXECUTE",
    "INPUT_TO_OBSERVE",
    "TOOL_TO_WORKFLOW",
    "WORKFLOW_TO_INFRASTRUCTURE",
    "DOCUMENT_TO_DATA",
    "DATA_TO_DECISION",
    "DECISION_TO_ACTION",
    "SERVICE_TO_ASSET",
    "ONE_TIME_TO_COMPOUNDING",
}

_ASSUMPTION_KEYS = {
    "assumption_id",
    "statement",
    "assumption_type",
    "scope",
    "why_it_exists",
    "supporting_claim_ids",
    "contradicting_claim_ids",
    "status",
}
_CHALLENGE_KEYS = {
    "assumption_id",
    "challenge_question",
    "remove_or_invert_test",
    "expected_effect_if_false",
    "new_opportunity_if_false",
    "new_risk_if_false",
}
_TRANSFORMATION_KEYS = {
    "transformation",
    "applicable",
    "reason",
    "resulting_reframe",
    "materiality",
}


def _require_text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _require_unique_string_list(field: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field} must be a list of non-empty strings")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


def _canonical_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:12]}"


def _claim_ids(graph: dict[str, Any]) -> set[str]:
    if not isinstance(graph, dict) or not isinstance(graph.get("records"), list):
        raise ValueError("graph must be a valid Evidence Graph object")
    return {
        record.get("claim_id")
        for record in graph["records"]
        if isinstance(record, dict) and isinstance(record.get("claim_id"), str)
    }


def _validate_claim_refs(graph: dict[str, Any], refs: list[str]) -> None:
    known = _claim_ids(graph)
    missing = sorted(set(refs) - known)
    if missing:
        raise ValueError(f"unknown Evidence Graph claim IDs: {', '.join(missing)}")


def create_assumption(
    *,
    graph: dict[str, Any],
    evolution_id: str,
    statement: str,
    assumption_type: str,
    scope: str,
    why_it_exists: str,
    supporting_claim_ids: list[str],
    contradicting_claim_ids: list[str],
    status: str,
) -> dict[str, Any]:
    """Create one evidence-aware assumption with a trusted deterministic ID."""
    evolution_id = _require_text("evolution_id", evolution_id)
    statement = _require_text("statement", statement)
    scope = _require_text("scope", scope)
    why_it_exists = _require_text("why_it_exists", why_it_exists)
    if assumption_type not in ASSUMPTION_TYPES:
        raise ValueError(f"assumption_type must be one of {sorted(ASSUMPTION_TYPES)}")
    if status not in ASSUMPTION_STATUSES:
        raise ValueError(f"status must be one of {sorted(ASSUMPTION_STATUSES)}")
    supporting = _require_unique_string_list("supporting_claim_ids", supporting_claim_ids)
    contradicting = _require_unique_string_list(
        "contradicting_claim_ids", contradicting_claim_ids
    )
    _validate_claim_refs(graph, supporting + contradicting)

    payload = {
        "evolution_id": evolution_id,
        "statement": statement,
        "assumption_type": assumption_type,
        "scope": scope,
        "why_it_exists": why_it_exists,
        "supporting_claim_ids": supporting,
        "contradicting_claim_ids": contradicting,
        "status": status,
    }
    return {
        "assumption_id": _canonical_id("assumption", payload),
        "statement": statement,
        "assumption_type": assumption_type,
        "scope": scope,
        "why_it_exists": why_it_exists,
        "supporting_claim_ids": supporting,
        "contradicting_claim_ids": contradicting,
        "status": status,
    }


def validate_assumption(record: dict[str, Any], graph: dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record) != _ASSUMPTION_KEYS:
        raise ValueError("assumption keys do not match the PR C contract")
    _require_text("assumption_id", record["assumption_id"])
    _require_text("statement", record["statement"])
    _require_text("scope", record["scope"])
    _require_text("why_it_exists", record["why_it_exists"])
    if record["assumption_type"] not in ASSUMPTION_TYPES:
        raise ValueError("invalid assumption_type")
    if record["status"] not in ASSUMPTION_STATUSES:
        raise ValueError("invalid assumption status")
    supporting = _require_unique_string_list(
        "supporting_claim_ids", record["supporting_claim_ids"]
    )
    contradicting = _require_unique_string_list(
        "contradicting_claim_ids", record["contradicting_claim_ids"]
    )
    _validate_claim_refs(graph, supporting + contradicting)


def create_assumption_challenge(
    *,
    assumption_id: str,
    challenge_question: str,
    remove_or_invert_test: str,
    expected_effect_if_false: str,
    new_opportunity_if_false: str,
    new_risk_if_false: str,
) -> dict[str, str]:
    """Create the explicit challenge applied to one assumption."""
    record = {
        "assumption_id": _require_text("assumption_id", assumption_id),
        "challenge_question": _require_text("challenge_question", challenge_question),
        "remove_or_invert_test": _require_text(
            "remove_or_invert_test", remove_or_invert_test
        ),
        "expected_effect_if_false": _require_text(
            "expected_effect_if_false", expected_effect_if_false
        ),
        "new_opportunity_if_false": _require_text(
            "new_opportunity_if_false", new_opportunity_if_false
        ),
        "new_risk_if_false": _require_text("new_risk_if_false", new_risk_if_false),
    }
    if set(record) != _CHALLENGE_KEYS:
        raise ValueError("assumption challenge contract mismatch")
    return record


def create_transformation_test(
    *,
    transformation: str,
    applicable: bool,
    reason: str,
    resulting_reframe: str,
    materiality: str,
) -> dict[str, Any]:
    """Record one perspective transformation attempt."""
    if transformation not in TRANSFORMATIONS:
        raise ValueError(f"transformation must be one of {sorted(TRANSFORMATIONS)}")
    if not isinstance(applicable, bool):
        raise ValueError("applicable must be a boolean")
    if materiality not in MATERIALITIES:
        raise ValueError(f"materiality must be one of {sorted(MATERIALITIES)}")
    record = {
        "transformation": transformation,
        "applicable": applicable,
        "reason": _require_text("reason", reason),
        "resulting_reframe": _require_text("resulting_reframe", resulting_reframe),
        "materiality": materiality,
    }
    return record


def validate_transformation_test(record: dict[str, Any]) -> None:
    if not isinstance(record, dict) or set(record) != _TRANSFORMATION_KEYS:
        raise ValueError("transformation test keys do not match the PR C contract")
    create_transformation_test(**deepcopy(record))


def audit_reframing_readiness(
    transformation_tests: list[dict[str, Any]], *, original_remains_strong: bool = False
) -> dict[str, Any]:
    """Require meaningful perspective testing before candidate generation."""
    if not isinstance(transformation_tests, list) or not transformation_tests:
        raise ValueError("transformation_tests must be a non-empty list")
    seen: set[str] = set()
    material: list[str] = []
    for record in transformation_tests:
        validate_transformation_test(record)
        name = record["transformation"]
        if name in seen:
            raise ValueError("transformation_tests must not repeat a transformation")
        seen.add(name)
        if record["applicable"] and record["materiality"] == "material":
            material.append(name)
    if not isinstance(original_remains_strong, bool):
        raise ValueError("original_remains_strong must be a boolean")
    return {
        "generation_ready": len(material) >= 2 or original_remains_strong,
        "material_transformations": material,
        "tested_count": len(transformation_tests),
        "original_remains_strong": original_remains_strong,
    }
