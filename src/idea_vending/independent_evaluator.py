"""Provider-neutral independent evaluator boundary for Idea Vending Machine v0.3 PR D."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.idea_vending.baseline_contract import validate_baseline
from src.idea_vending.candidate_forge import validate_candidate
from src.idea_vending.evaluator_contract import validate_critique

EVALUATION_REQUEST_KEYS = {
    "evolution_id",
    "baseline",
    "candidates",
    "evidence_graph",
    "candidate_admission_audit",
    "feasibility_artifacts",
    "collision_state",
    "evaluator_policy",
}
PROVIDER_OUTPUT_KEYS = {"critiques"}


def _validate_inputs(
    *,
    baseline: dict[str, Any],
    candidates: list[dict[str, Any]],
    graph: dict[str, Any],
    candidate_admission_audit: dict[str, Any] | None = None,
) -> None:
    validate_baseline(baseline, graph)
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    ids: list[str] = []
    for candidate in candidates:
        validate_candidate(candidate, graph)
        ids.append(candidate["candidate_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs must be unique")
    if graph.get("evolution_id") != baseline["evolution_id"]:
        raise ValueError("evolution_id mismatch between graph and baseline")
    if candidate_admission_audit is not None:
        if not isinstance(candidate_admission_audit, dict):
            raise ValueError("candidate_admission_audit must be a dictionary")
        if candidate_admission_audit.get("forge_ready") is not True:
            raise ValueError("candidate admission audit must be forge_ready")


def build_evaluation_request(
    *,
    baseline: dict[str, Any],
    candidates: list[dict[str, Any]],
    graph: dict[str, Any],
    candidate_admission_audit: dict[str, Any],
    feasibility_artifacts: dict[str, Any],
    collision_state: dict[str, Any],
) -> dict[str, Any]:
    """Build a deep-copied request that carries no preselected winner or official verdict."""
    _validate_inputs(
        baseline=baseline,
        candidates=candidates,
        graph=graph,
        candidate_admission_audit=candidate_admission_audit,
    )
    if not isinstance(feasibility_artifacts, dict):
        raise ValueError("feasibility_artifacts must be a dictionary")
    if not isinstance(collision_state, dict):
        raise ValueError("collision_state must be a dictionary")

    request = {
        "evolution_id": baseline["evolution_id"],
        "baseline": baseline,
        "candidates": candidates,
        "evidence_graph": graph,
        "candidate_admission_audit": candidate_admission_audit,
        "feasibility_artifacts": feasibility_artifacts,
        "collision_state": collision_state,
        "evaluator_policy": {
            "independent_evaluation": True,
            "generator_scores_authoritative": False,
            "official_fields_forbidden": True,
        },
    }
    return deepcopy(request)


def ingest_evaluator_output(
    raw: dict[str, Any],
    *,
    graph: dict[str, Any],
    baseline: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate provider output while preserving it as untrusted, copied data."""
    _validate_inputs(baseline=baseline, candidates=candidates, graph=graph)
    if not isinstance(raw, dict) or set(raw) != PROVIDER_OUTPUT_KEYS:
        raise ValueError("provider output keys do not match the PR D contract")
    critiques = raw["critiques"]
    if not isinstance(critiques, list):
        raise ValueError("provider output critiques must be a list")

    candidate_ids = {candidate["candidate_id"] for candidate in candidates}
    known_ids = {baseline["baseline_id"], *candidate_ids}
    copied = deepcopy(critiques)
    for critique in copied:
        validate_critique(critique, graph)
        target_id = critique["target_id"]
        if target_id not in known_ids:
            raise ValueError(f"unknown evaluator target_id: {target_id}")
        if target_id == baseline["baseline_id"] and critique["target_type"] != "baseline":
            raise ValueError("baseline target_id must use target_type=baseline")
        if target_id in candidate_ids and critique["target_type"] != "candidate":
            raise ValueError("candidate target_id must use target_type=candidate")

    return {
        "untrusted_provider_output": True,
        "critiques": copied,
    }
