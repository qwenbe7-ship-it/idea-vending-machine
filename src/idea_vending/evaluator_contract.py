"""Provider-neutral independent-evaluator contract for Idea Vending Machine v0.3 PR D."""

from __future__ import annotations

from typing import Any

EVALUATION_DIMENSIONS = {
    "problem_evidence",
    "buyer_economics",
    "structural_differentiation",
    "competitive_collision",
    "automation_leverage",
    "technical_feasibility",
    "operational_reliability",
    "regulatory_security_data_risk",
    "distribution_feasibility",
    "defensibility_compounding",
}
STATUSES = {"strong", "mixed", "weak", "unknown"}
RECOMMENDATIONS = {"advance", "revise", "hold", "reject"}
BLOCKER_MATERIALITIES = {"minor", "material", "hard"}
TARGET_TYPES = {"baseline", "candidate"}

DIMENSION_KEYS = {
    "dimension",
    "status",
    "rationale",
    "supporting_claim_ids",
    "contradicting_claim_ids",
    "material_unknowns",
    "blockers",
}
BLOCKER_KEYS = {"reason", "materiality", "evidence_claim_ids", "resolvable"}
CRITIQUE_KEYS = {
    "target_type",
    "target_id",
    "dimensions",
    "strongest_reason_for",
    "strongest_reason_against",
    "unacceptable_conditions",
    "cheapest_next_validation",
    "recommendation",
}


def _text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _unique_text_list(field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


def _known_claim_ids(graph: dict[str, Any]) -> set[str]:
    if not isinstance(graph, dict) or not isinstance(graph.get("records"), list):
        raise ValueError("graph must be a valid Evidence Graph object")
    return {
        record.get("claim_id")
        for record in graph["records"]
        if isinstance(record, dict) and isinstance(record.get("claim_id"), str)
    }


def _validate_claim_refs(graph: dict[str, Any], refs: list[str]) -> None:
    missing = sorted(set(refs) - _known_claim_ids(graph))
    if missing:
        raise ValueError(f"unknown Evidence Graph claim IDs: {', '.join(missing)}")


def _validate_blocker(blocker: Any, graph: dict[str, Any]) -> None:
    if not isinstance(blocker, dict) or set(blocker) != BLOCKER_KEYS:
        raise ValueError("blocker keys do not match the PR D contract")
    _text("blocker.reason", blocker["reason"])
    if blocker["materiality"] not in BLOCKER_MATERIALITIES:
        raise ValueError(
            f"blocker.materiality must be one of {sorted(BLOCKER_MATERIALITIES)}"
        )
    refs = _unique_text_list("blocker.evidence_claim_ids", blocker["evidence_claim_ids"])
    if not refs:
        raise ValueError("blocker.evidence_claim_ids must not be empty")
    _validate_claim_refs(graph, refs)
    if not isinstance(blocker["resolvable"], bool):
        raise ValueError("blocker.resolvable must be boolean")


def validate_dimension_assessment(item: dict[str, Any], graph: dict[str, Any]) -> None:
    if not isinstance(item, dict) or set(item) != DIMENSION_KEYS:
        raise ValueError("dimension assessment keys do not match the PR D contract")
    if item["dimension"] not in EVALUATION_DIMENSIONS:
        raise ValueError("dimension must be canonical")
    if item["status"] not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    _text("rationale", item["rationale"])
    supporting = _unique_text_list("supporting_claim_ids", item["supporting_claim_ids"])
    contradicting = _unique_text_list(
        "contradicting_claim_ids", item["contradicting_claim_ids"]
    )
    _validate_claim_refs(graph, supporting + contradicting)
    _unique_text_list("material_unknowns", item["material_unknowns"])
    if not isinstance(item["blockers"], list):
        raise ValueError("blockers must be a list")
    for blocker in item["blockers"]:
        _validate_blocker(blocker, graph)


def create_critique(
    *,
    graph: dict[str, Any],
    target_type: str,
    target_id: str,
    dimensions: list[dict[str, Any]],
    strongest_reason_for: str,
    strongest_reason_against: str,
    unacceptable_conditions: list[str],
    cheapest_next_validation: str,
    recommendation: str,
) -> dict[str, Any]:
    critique = {
        "target_type": target_type,
        "target_id": target_id,
        "dimensions": dimensions,
        "strongest_reason_for": strongest_reason_for,
        "strongest_reason_against": strongest_reason_against,
        "unacceptable_conditions": unacceptable_conditions,
        "cheapest_next_validation": cheapest_next_validation,
        "recommendation": recommendation,
    }
    validate_critique(critique, graph)
    return critique


def validate_critique(critique: dict[str, Any], graph: dict[str, Any]) -> None:
    if not isinstance(critique, dict) or set(critique) != CRITIQUE_KEYS:
        raise ValueError("critique keys do not match the PR D contract")
    if critique["target_type"] not in TARGET_TYPES:
        raise ValueError("target_type must be baseline or candidate")
    _text("target_id", critique["target_id"])
    if not isinstance(critique["dimensions"], list):
        raise ValueError("dimensions must be a list")
    dimensions = []
    for item in critique["dimensions"]:
        validate_dimension_assessment(item, graph)
        dimensions.append(item["dimension"])
    if len(dimensions) != len(EVALUATION_DIMENSIONS) or set(dimensions) != EVALUATION_DIMENSIONS:
        raise ValueError("critique must contain every evaluation dimension exactly once")
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("critique must contain every evaluation dimension exactly once")
    _text("strongest_reason_for", critique["strongest_reason_for"])
    _text("strongest_reason_against", critique["strongest_reason_against"])
    _unique_text_list("unacceptable_conditions", critique["unacceptable_conditions"])
    _text("cheapest_next_validation", critique["cheapest_next_validation"])
    if critique["recommendation"] not in RECOMMENDATIONS:
        raise ValueError(
            f"recommendation must be one of {sorted(RECOMMENDATIONS)}"
        )
