"""Deterministic hard gates and decision helpers for Idea Vending Machine v0.3 PR D."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.evolution_schema import validate_evolution_state

ANCHOR_DIMENSIONS = {
    "problem_evidence",
    "buyer_economics",
    "structural_differentiation",
    "technical_feasibility",
}
_STATUS_ORDER = {"weak": 0, "mixed": 1, "strong": 2}
_FEASIBILITY_LEVELS = {"T1", "T2", "T3", "T4", "T5"}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_DECISIONS = {"GO", "MODIFY", "HOLD", "KILL"}
_DECISION_RESULT_KEYS = {
    "decision",
    "confidence",
    "selected_concept_id",
    "decision_reasons",
    "next_validation",
}


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


def _validate_classification_result(result: dict[str, Any], field: str) -> None:
    if not isinstance(result, dict):
        raise ValueError(f"{field} must be a dictionary")
    if result.get("classification") not in {"eligible", "hold", "eliminated"}:
        raise ValueError(f"{field}.classification is invalid")
    for list_field in ("hold_reasons", "decisive_failure_reasons"):
        value = result.get(list_field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError(f"{field}.{list_field} must be a string list")


def _critique_ids(critiques: list[dict[str, Any]]) -> list[str]:
    if not isinstance(critiques, list):
        raise ValueError("candidate_critiques must be a list")
    ids: list[str] = []
    for critique in critiques:
        target_id = critique.get("target_id") if isinstance(critique, dict) else None
        if not isinstance(target_id, str) or not target_id.strip():
            raise ValueError("candidate critique target_id must be a non-empty string")
        _dimension_map(critique)
        ids.append(target_id)
    if len(ids) != len(set(ids)):
        raise ValueError("candidate critique target IDs must be unique")
    return ids


def _strictly_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return True only when left is never worse and improves an anchor dimension."""
    left_map = _dimension_map(left)
    right_map = _dimension_map(right)
    better: list[str] = []
    for name in EVALUATION_DIMENSIONS:
        left_status = left_map[name].get("status")
        right_status = right_map[name].get("status")
        if left_status == "unknown" or right_status == "unknown":
            return False
        if left_status not in _STATUS_ORDER or right_status not in _STATUS_ORDER:
            raise ValueError("dimension status must be strong, mixed, weak, or unknown")
        if _STATUS_ORDER[left_status] < _STATUS_ORDER[right_status]:
            return False
        if _STATUS_ORDER[left_status] > _STATUS_ORDER[right_status]:
            better.append(name)
    return bool(set(better) & ANCHOR_DIMENSIONS)


def _hold_result(reason: str, next_validation: str) -> dict[str, Any]:
    return {
        "decision": "HOLD",
        "confidence": "low",
        "selected_concept_id": None,
        "decision_reasons": [reason],
        "next_validation": next_validation,
    }


def decide_evolution(
    *,
    baseline_critique: dict[str, Any],
    candidate_critiques: list[dict[str, Any]],
    baseline_classification: dict[str, Any],
    candidate_classifications: dict[str, dict[str, Any]],
    baseline_confidence: str,
    candidate_confidences: dict[str, str],
    comparison_validation_action: str,
) -> dict[str, Any]:
    """Derive the official GO/MODIFY/HOLD/KILL verdict conservatively."""
    baseline_id = baseline_critique.get("target_id")
    if not isinstance(baseline_id, str) or not baseline_id.strip():
        raise ValueError("baseline critique target_id must be a non-empty string")
    _dimension_map(baseline_critique)
    candidate_ids = _critique_ids(candidate_critiques)
    _validate_classification_result(baseline_classification, "baseline_classification")
    if set(candidate_classifications) != set(candidate_ids):
        raise ValueError("candidate_classifications must match candidate critique IDs")
    if set(candidate_confidences) != set(candidate_ids):
        raise ValueError("candidate_confidences must match candidate critique IDs")
    for candidate_id, result in candidate_classifications.items():
        _validate_classification_result(result, f"candidate_classifications.{candidate_id}")
    if baseline_confidence not in _CONFIDENCE_LEVELS:
        raise ValueError("baseline_confidence is invalid")
    if any(value not in _CONFIDENCE_LEVELS for value in candidate_confidences.values()):
        raise ValueError("candidate confidence is invalid")
    if not isinstance(comparison_validation_action, str) or not comparison_validation_action.strip():
        raise ValueError("comparison_validation_action must be a non-empty string")

    all_classifications = [baseline_classification, *candidate_classifications.values()]
    if all(result["classification"] == "eliminated" for result in all_classifications):
        decisive = [
            reason
            for result in all_classifications
            for reason in result["decisive_failure_reasons"]
        ]
        if decisive and all(result["decisive_failure_reasons"] for result in all_classifications):
            confidences = [baseline_confidence, *candidate_confidences.values()]
            confidence = "high" if all(value == "high" for value in confidences) else (
                "medium" if any(value in {"high", "medium"} for value in confidences) else "low"
            )
            return {
                "decision": "KILL",
                "confidence": confidence,
                "selected_concept_id": None,
                "decision_reasons": decisive,
                "next_validation": None,
            }
        return _hold_result(
            "Options are eliminated without complete evidence-backed decisive failure reasons.",
            comparison_validation_action,
        )

    if baseline_classification["classification"] == "hold" or any(
        result["classification"] == "hold"
        for result in candidate_classifications.values()
    ):
        return _hold_result(
            "Decision-critical uncertainty remains in at least one live option.",
            comparison_validation_action,
        )

    critique_by_id = {item["target_id"]: item for item in candidate_critiques}
    qualifying: list[dict[str, Any]] = []
    low_confidence_qualifier = False
    for candidate_id in candidate_ids:
        if candidate_classifications[candidate_id]["classification"] != "eligible":
            continue
        critique = critique_by_id[candidate_id]
        delta = compare_evolution_delta(baseline_critique, critique)
        if not delta["material_improvement"]:
            continue
        if candidate_confidences[candidate_id] == "low":
            low_confidence_qualifier = True
            continue
        qualifying.append(critique)

    if low_confidence_qualifier:
        return _hold_result(
            "A materially improved candidate exists but evidence confidence is too low for a positive decision.",
            comparison_validation_action,
        )

    if len(qualifying) == 1:
        selected_id = qualifying[0]["target_id"]
        return {
            "decision": "MODIFY",
            "confidence": candidate_confidences[selected_id],
            "selected_concept_id": selected_id,
            "decision_reasons": ["One eligible evolved candidate materially improves the baseline."],
            "next_validation": None,
        }

    if len(qualifying) > 1:
        dominant = [
            candidate
            for candidate in qualifying
            if all(
                candidate["target_id"] == other["target_id"]
                or _strictly_dominates(candidate, other)
                for other in qualifying
            )
        ]
        if len(dominant) == 1:
            selected_id = dominant[0]["target_id"]
            return {
                "decision": "MODIFY",
                "confidence": candidate_confidences[selected_id],
                "selected_concept_id": selected_id,
                "decision_reasons": ["One evolved candidate strictly dominates every other qualifying candidate."],
                "next_validation": None,
            }
        return _hold_result(
            "Multiple materially improved candidates remain indistinguishable under the strict-dominance rule.",
            comparison_validation_action,
        )

    if baseline_classification["classification"] == "eligible":
        if baseline_confidence == "low":
            return _hold_result(
                "The baseline is eligible but confidence is too low for GO.",
                comparison_validation_action,
            )
        return {
            "decision": "GO",
            "confidence": baseline_confidence,
            "selected_concept_id": None,
            "decision_reasons": ["The original idea remains eligible and no evolved candidate materially improves it."],
            "next_validation": None,
        }

    return _hold_result(
        "No option is sufficiently decision-ready for a positive or evidence-backed negative verdict.",
        comparison_validation_action,
    )


def _validate_decision_result(result: dict[str, Any]) -> None:
    if not isinstance(result, dict) or set(result) != _DECISION_RESULT_KEYS:
        raise ValueError("decision result keys do not match the PR D contract")
    if result["decision"] not in _DECISIONS:
        raise ValueError("decision result contains an invalid decision")
    if result["confidence"] not in _CONFIDENCE_LEVELS:
        raise ValueError("decision result contains an invalid confidence")
    if result["decision"] in {"GO", "MODIFY"} and result["confidence"] == "low":
        raise ValueError("GO/MODIFY cannot have low confidence")
    if not isinstance(result["decision_reasons"], list) or not result["decision_reasons"] or not all(
        isinstance(item, str) and item.strip() for item in result["decision_reasons"]
    ):
        raise ValueError("decision_reasons must be a non-empty string list")
    if result["next_validation"] is not None and (
        not isinstance(result["next_validation"], str) or not result["next_validation"].strip()
    ):
        raise ValueError("next_validation must be a non-empty string or null")
    if result["decision"] == "MODIFY":
        if not isinstance(result["selected_concept_id"], str) or not result["selected_concept_id"].strip():
            raise ValueError("MODIFY requires selected_concept_id")
    elif result["selected_concept_id"] is not None:
        raise ValueError("only MODIFY may set selected_concept_id")


def apply_decision_to_state(
    state: dict[str, Any],
    decision_result: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a trusted PR D result without ever granting human approval."""
    validate_evolution_state(state)
    _validate_decision_result(decision_result)
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be a dictionary")
        candidate_id = candidate.get("candidate_id")
        concept = candidate.get("one_sentence_concept")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError("candidate_id must be a non-empty string")
        if not isinstance(concept, str) or not concept.strip():
            raise ValueError("candidate one_sentence_concept must be non-empty")
        if candidate_id in candidate_by_id:
            raise ValueError("candidate IDs must be unique")
        candidate_by_id[candidate_id] = candidate

    updated = deepcopy(state)
    human_decision = updated["human_decision"]
    decision = decision_result["decision"]
    updated["decision"] = decision
    updated["confidence"] = decision_result["confidence"]

    if decision == "MODIFY":
        selected_id = decision_result["selected_concept_id"]
        if selected_id not in candidate_by_id:
            raise ValueError("selected_concept_id does not match a supplied candidate")
        updated["selected_concept_id"] = selected_id
        updated["evolved_idea"] = candidate_by_id[selected_id]["one_sentence_concept"]
    else:
        updated["selected_concept_id"] = None
        updated["evolved_idea"] = None

    updated["human_decision"] = human_decision
    validate_evolution_state(updated)
    return updated
