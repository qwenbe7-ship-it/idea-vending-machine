"""Deterministic hard gates and decision helpers for Idea Vending Machine v0.3 PR D."""

from __future__ import annotations

from typing import Any

from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS

ANCHOR_DIMENSIONS = {
    "problem_evidence",
    "buyer_economics",
    "structural_differentiation",
    "technical_feasibility",
}
_STATUS_ORDER = {"weak": 0, "mixed": 1, "strong": 2}
_FEASIBILITY_LEVELS = {"T1", "T2", "T3", "T4", "T5"}


def _dimension_map(critique: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(critique, dict) or not isinstance(critique.get("dimensions"), list):
        raise ValueError("critique must contain dimensions")
    result: dict[str, dict[str, Any]] = {}
    for item in critique["dimensions"]:
        if not isinstance(item, dict) or item.get("dimension") not in EVALUATION_DIMENSIONS:
            raise ValueError("critique contains an invalid evaluation dimension")
        if item["dimension"] in result:
            raise ValueError("critique contains duplicate evaluation dimensions")
        result[item["dimension"]] = item
    if set(result) != EVALUATION_DIMENSIONS:
        raise ValueError("critique must contain every evaluation dimension")
    return result


def _material_unknowns(critique: dict[str, Any]) -> list[str]:
    unknowns: list[str] = []
    for item in _dimension_map(critique).values():
        if item.get("status") == "unknown":
            unknowns.append(item["dimension"])
        for unknown in item.get("material_unknowns", []):
            if unknown not in unknowns:
                unknowns.append(unknown)
    return unknowns


def _material_collisions(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(requests, list):
        raise ValueError("unresolved_collision_requests must be a list")
    return [
        request
        for request in requests
        if isinstance(request, dict) and request.get("materiality") == "material"
    ]


def _blockers(critique: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for item in _dimension_map(critique).values():
        for blocker in item.get("blockers", []):
            if isinstance(blocker, dict):
                blockers.append(blocker)
    return blockers


def _validate_evidence_audit(audit: dict[str, Any]) -> None:
    if not isinstance(audit, dict):
        raise ValueError("evidence_audit must be a dictionary")
    required = {
        "decision_ready",
        "counter_evidence_complete",
        "freshness_ready",
        "tier_ab_support_ready",
        "noncritical_secondary_only",
    }
    if not required.issubset(audit):
        raise ValueError("evidence_audit is missing required readiness fields")
    for key in required:
        if not isinstance(audit[key], bool):
            raise ValueError(f"evidence_audit.{key} must be boolean")


def _validate_feasibility(artifact: dict[str, Any]) -> str:
    if not isinstance(artifact, dict):
        raise ValueError("feasibility_artifact must be a dictionary")
    level = artifact.get("level")
    if level not in _FEASIBILITY_LEVELS:
        raise ValueError(f"feasibility level must be one of {sorted(_FEASIBILITY_LEVELS)}")
    for field in ("blocking_dependency_resolved", "resolution_path_exists"):
        if field in artifact and not isinstance(artifact[field], bool):
            raise ValueError(f"feasibility_artifact.{field} must be boolean")
    return level


def classify_option(
    critique: dict[str, Any],
    *,
    unresolved_collision_requests: list[dict[str, Any]],
    feasibility_artifact: dict[str, Any],
    evidence_audit: dict[str, Any],
) -> dict[str, Any]:
    """Classify an option as eligible, hold, or eliminated using fail-closed gates."""
    _validate_evidence_audit(evidence_audit)
    level = _validate_feasibility(feasibility_artifact)
    unknowns = _material_unknowns(critique)
    collisions = _material_collisions(unresolved_collision_requests)
    blockers = _blockers(critique)

    hold_reasons: list[str] = []
    decisive_failure_reasons: list[str] = []

    hard_unresolvable = [
        blocker
        for blocker in blockers
        if blocker.get("materiality") == "hard" and blocker.get("resolvable") is False
    ]
    if hard_unresolvable:
        decisive_failure_reasons.extend(
            blocker.get("reason", "hard blocker") for blocker in hard_unresolvable
        )

    if level == "T1" and not feasibility_artifact.get("resolution_path_exists", True):
        decisive_failure_reasons.append("T1 feasibility with no plausible resolution path")

    if decisive_failure_reasons:
        classification = "eliminated"
    else:
        if unknowns:
            hold_reasons.append("material_unknowns")
        if collisions:
            hold_reasons.append("material_collision")
        if any(
            blocker.get("materiality") in {"material", "hard"}
            for blocker in blockers
        ):
            hold_reasons.append("resolvable_blocker")
        if not evidence_audit["decision_ready"]:
            hold_reasons.append("evidence_not_ready")
        if not evidence_audit["counter_evidence_complete"]:
            hold_reasons.append("counter_evidence_incomplete")
        if not evidence_audit["freshness_ready"]:
            hold_reasons.append("evidence_stale")
        if level == "T1":
            hold_reasons.append("T1_feasibility")
        elif level == "T2" and not feasibility_artifact.get(
            "blocking_dependency_resolved", False
        ):
            hold_reasons.append("T2_unresolved_dependency")
        classification = "hold" if hold_reasons else "eligible"

    return {
        "classification": classification,
        "hold_reasons": list(dict.fromkeys(hold_reasons)),
        "decisive_failure_reasons": decisive_failure_reasons,
        "material_unknowns": unknowns,
        "material_collision_count": len(collisions),
        "feasibility_level": level,
    }


def derive_confidence(
    critique: dict[str, Any],
    *,
    classification: str,
    unresolved_collision_requests: list[dict[str, Any]],
    evidence_audit: dict[str, Any],
) -> str:
    """Derive confidence independently from the verdict or provider recommendation."""
    if classification not in {"eligible", "hold", "eliminated"}:
        raise ValueError("classification must be eligible, hold, or eliminated")
    _validate_evidence_audit(evidence_audit)
    unknowns = _material_unknowns(critique)
    collisions = _material_collisions(unresolved_collision_requests)
    if unknowns or collisions or not evidence_audit["decision_ready"]:
        return "low"
    ready_core = (
        evidence_audit["counter_evidence_complete"]
        and evidence_audit["freshness_ready"]
        and evidence_audit["tier_ab_support_ready"]
    )
    if ready_core and not evidence_audit["noncritical_secondary_only"]:
        return "high"
    if ready_core:
        return "medium"
    return "low"


def compare_evolution_delta(
    baseline_critique: dict[str, Any], candidate_critique: dict[str, Any]
) -> dict[str, Any]:
    """Compare normalized dimension states without weighted totals or pseudo-scores."""
    baseline = _dimension_map(baseline_critique)
    candidate = _dimension_map(candidate_critique)
    if any(
        baseline[name].get("status") == "unknown"
        or candidate[name].get("status") == "unknown"
        for name in EVALUATION_DIMENSIONS
    ):
        return {
            "comparable": False,
            "material_improvement": False,
            "better_dimensions": [],
            "worse_dimensions": [],
            "anchor_improvements": [],
        }

    better: list[str] = []
    worse: list[str] = []
    for name in sorted(EVALUATION_DIMENSIONS):
        baseline_status = baseline[name].get("status")
        candidate_status = candidate[name].get("status")
        if baseline_status not in _STATUS_ORDER or candidate_status not in _STATUS_ORDER:
            raise ValueError("dimension status must be strong, mixed, weak, or unknown")
        if _STATUS_ORDER[candidate_status] > _STATUS_ORDER[baseline_status]:
            better.append(name)
        elif _STATUS_ORDER[candidate_status] < _STATUS_ORDER[baseline_status]:
            worse.append(name)

    anchors = [name for name in better if name in ANCHOR_DIMENSIONS]
    return {
        "comparable": True,
        "material_improvement": len(better) >= 2 and bool(anchors),
        "better_dimensions": better,
        "worse_dimensions": worse,
        "anchor_improvements": anchors,
    }
