"""Deterministic per-candidate Reality Verdicts for v0.3 E2A."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS

REALITY_VERDICTS = {"ADVANCE", "REVISE", "HOLD", "REJECT"}
_CONFIDENCE = {"high", "medium", "low"}
_CLASSIFICATIONS = {"eligible", "hold", "eliminated"}
_UNCERTAINTY_REASONS = {
    "material_unknowns",
    "material_collision",
    "evidence_not_ready",
    "counter_evidence_incomplete",
    "evidence_stale",
    "T1_feasibility",
    "T2_unresolved_dependency",
}


def _text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _dimension_map(critique: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(critique, dict) or not isinstance(critique.get("dimensions"), list):
        raise ValueError("critique must contain dimensions")
    mapped: dict[str, dict[str, Any]] = {}
    for item in critique["dimensions"]:
        if not isinstance(item, dict):
            raise ValueError("dimension assessment must be a dictionary")
        name = item.get("dimension")
        status = item.get("status")
        if name not in EVALUATION_DIMENSIONS or name in mapped:
            raise ValueError("critique dimensions must be canonical and unique")
        if status not in {"strong", "mixed", "weak", "unknown"}:
            raise ValueError("dimension status is invalid")
        mapped[name] = item
    if set(mapped) != EVALUATION_DIMENSIONS:
        raise ValueError("critique must contain every evaluation dimension")
    return mapped


def _unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def derive_reality_assessment(
    *,
    candidate: dict[str, Any],
    critique: dict[str, Any],
    gate_result: dict[str, Any],
    confidence: str,
) -> dict[str, Any]:
    """Derive one conservative Reality Verdict without using provider recommendation."""
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a dictionary")
    candidate_id = _text("candidate.candidate_id", candidate.get("candidate_id"))
    family = _text("candidate.family", candidate.get("family"))
    name = _text("candidate.name", candidate.get("name"))
    concept = _text("candidate.one_sentence_concept", candidate.get("one_sentence_concept"))
    if critique.get("target_id") != candidate_id or critique.get("target_type") != "candidate":
        raise ValueError("critique must target the candidate")
    dimensions = _dimension_map(critique)

    if not isinstance(gate_result, dict):
        raise ValueError("gate_result must be a dictionary")
    classification = gate_result.get("classification")
    if classification not in _CLASSIFICATIONS:
        raise ValueError("gate_result.classification is invalid")
    hold_reasons = gate_result.get("hold_reasons")
    decisive = gate_result.get("decisive_failure_reasons")
    if not isinstance(hold_reasons, list) or not isinstance(decisive, list):
        raise ValueError("gate_result reason fields must be lists")
    if confidence not in _CONFIDENCE:
        raise ValueError("confidence must be high, medium, or low")

    material_unknowns: list[str] = []
    blockers: list[dict[str, Any]] = []
    evidence_claim_ids: list[str] = []
    statuses: dict[str, str] = {}
    for dimension in sorted(EVALUATION_DIMENSIONS):
        item = dimensions[dimension]
        statuses[dimension] = item["status"]
        if item["status"] == "unknown":
            material_unknowns.append(dimension)
        material_unknowns.extend(item.get("material_unknowns", []))
        evidence_claim_ids.extend(item.get("supporting_claim_ids", []))
        evidence_claim_ids.extend(item.get("contradicting_claim_ids", []))
        for blocker in item.get("blockers", []):
            if isinstance(blocker, dict) and blocker.get("materiality") in {"material", "hard"}:
                blockers.append(deepcopy(blocker))
                evidence_claim_ids.extend(blocker.get("evidence_claim_ids", []))

    material_unknowns = _unique_strings(material_unknowns)
    evidence_claim_ids = _unique_strings(evidence_claim_ids)
    unresolvable_hard = any(
        blocker.get("materiality") == "hard" and blocker.get("resolvable") is False
        for blocker in blockers
    )
    resolvable_material = any(
        blocker.get("materiality") in {"material", "hard"}
        and blocker.get("resolvable") is True
        for blocker in blockers
    )
    uncertainty_gate = bool(set(hold_reasons) & _UNCERTAINTY_REASONS)
    has_unknown_dimension = any(status == "unknown" for status in statuses.values())
    has_weak_dimension = any(status == "weak" for status in statuses.values())

    if material_unknowns or has_unknown_dimension or uncertainty_gate:
        verdict = "HOLD"
    elif classification == "eliminated" and (unresolvable_hard or decisive):
        verdict = "REJECT"
    elif classification == "hold" and resolvable_material:
        verdict = "REVISE"
    elif classification == "hold":
        verdict = "HOLD"
    elif confidence == "low":
        verdict = "HOLD"
    elif has_weak_dimension or resolvable_material:
        verdict = "REVISE"
    elif classification == "eligible":
        verdict = "ADVANCE"
    else:
        verdict = "HOLD"

    return {
        "candidate_id": candidate_id,
        "family": family,
        "name": name,
        "one_sentence_concept": concept,
        "reality_verdict": verdict,
        "confidence": confidence,
        "strongest_reason_for": _text(
            "critique.strongest_reason_for", critique.get("strongest_reason_for")
        ),
        "strongest_reason_against": _text(
            "critique.strongest_reason_against", critique.get("strongest_reason_against")
        ),
        "dimension_statuses": statuses,
        "hard_or_material_blockers": blockers,
        "material_unknowns": material_unknowns,
        "cheapest_next_validation": _text(
            "critique.cheapest_next_validation", critique.get("cheapest_next_validation")
        ),
        "evidence_claim_ids": evidence_claim_ids,
    }
