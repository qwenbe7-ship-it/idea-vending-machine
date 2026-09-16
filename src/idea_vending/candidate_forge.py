"""Deterministic candidate admission contracts for Idea Vending Machine v0.3 PR C."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from itertools import combinations
from typing import Any

from src.idea_vending.reframing import TRANSFORMATIONS

CANDIDATE_FAMILIES = {
    "adjacent_innovation",
    "category_shift",
    "zero_based_reinvention",
    "axion_candidate",
}
VALUE_CHAIN_KEYS = {
    "current_constraint",
    "intervention",
    "workflow_or_incentive_change",
    "operational_or_economic_effect",
    "buyer_value",
    "value_capture",
}
DIVERSITY_DIMENSIONS = (
    "primary_buyer",
    "problem_reframe",
    "workflow_after",
    "value_creation_chain",
    "value_capture_model",
    "transformations_used",
    "mechanism_transfer_ids",
)
COLLISION_MATERIALITIES = {"minor", "material"}
COLLISION_CATEGORIES = {
    "prior_art",
    "competitors",
    "buyer_evidence",
    "pricing",
    "regulation",
    "technical_dependency",
    "failure_or_blockers",
}

CANDIDATE_KEYS = {
    "candidate_id",
    "family",
    "name",
    "one_sentence_concept",
    "problem_reframe",
    "primary_buyer",
    "user",
    "job_to_be_done",
    "assumptions_broken",
    "transformations_used",
    "mechanism_transfer_ids",
    "workflow_before",
    "workflow_after",
    "value_creation_chain",
    "value_capture_model",
    "automation_thesis",
    "defensibility_thesis",
    "compounding_effect",
    "critical_dependencies",
    "new_risks",
    "evidence_claim_ids",
    "unknowns",
    "validation_questions",
}

_ASSUMPTION_ID_RE = re.compile(r"^assumption_[A-Za-z0-9_-]{6,64}$")
_TRANSFER_ID_RE = re.compile(r"^transfer_[A-Za-z0-9_-]{6,64}$")
_CANDIDATE_ID_RE = re.compile(r"^candidate_[0-9a-f]{12}$")


def _text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _unique_text_list(field: str, value: Any, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field} must be a non-empty list")
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


def _stable_hash(prefix: str, payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:12]}"


def _stable_candidate_id(payload: dict[str, Any]) -> str:
    return _stable_hash("candidate", payload)


def _normalize_value_chain(value_chain: Any) -> dict[str, str]:
    if not isinstance(value_chain, dict) or set(value_chain) != VALUE_CHAIN_KEYS:
        raise ValueError("value_creation_chain must contain every exact causal link")
    return {
        key: _text(f"value_creation_chain.{key}", value_chain[key])
        for key in sorted(VALUE_CHAIN_KEYS)
    }


def _validate_claim_refs(graph: dict[str, Any], refs: list[str]) -> None:
    missing = sorted(set(refs) - _known_claim_ids(graph))
    if missing:
        raise ValueError(f"unknown Evidence Graph claim IDs: {', '.join(missing)}")


def create_candidate(
    *,
    graph: dict[str, Any],
    family: str,
    name: str,
    one_sentence_concept: str,
    problem_reframe: str,
    primary_buyer: str,
    user: str,
    job_to_be_done: str,
    assumptions_broken: list[str],
    transformations_used: list[str],
    mechanism_transfer_ids: list[str],
    workflow_before: str,
    workflow_after: str,
    value_creation_chain: dict[str, Any],
    value_capture_model: str,
    automation_thesis: str,
    defensibility_thesis: str,
    compounding_effect: str,
    critical_dependencies: list[str],
    new_risks: list[str],
    evidence_claim_ids: list[str],
    unknowns: list[str],
    validation_questions: list[str],
) -> dict[str, Any]:
    """Create one candidate after deterministic schema/evidence validation."""
    if family not in CANDIDATE_FAMILIES:
        raise ValueError(f"family must be one of {sorted(CANDIDATE_FAMILIES)}")

    assumptions = _unique_text_list("assumptions_broken", assumptions_broken)
    for assumption_id in assumptions:
        if not _ASSUMPTION_ID_RE.fullmatch(assumption_id):
            raise ValueError("assumptions_broken must contain assumption_ identifiers")

    transformations = _unique_text_list(
        "transformations_used", transformations_used, allow_empty=False
    )
    invalid_transformations = sorted(set(transformations) - TRANSFORMATIONS)
    if invalid_transformations:
        raise ValueError(f"unknown transformations: {', '.join(invalid_transformations)}")

    transfer_ids = _unique_text_list("mechanism_transfer_ids", mechanism_transfer_ids)
    for transfer_id in transfer_ids:
        if not _TRANSFER_ID_RE.fullmatch(transfer_id):
            raise ValueError("mechanism_transfer_ids must contain transfer_ identifiers")

    evidence_refs = _unique_text_list("evidence_claim_ids", evidence_claim_ids)
    _validate_claim_refs(graph, evidence_refs)

    payload = {
        "family": family,
        "name": _text("name", name),
        "one_sentence_concept": _text("one_sentence_concept", one_sentence_concept),
        "problem_reframe": _text("problem_reframe", problem_reframe),
        "primary_buyer": _text("primary_buyer", primary_buyer),
        "user": _text("user", user),
        "job_to_be_done": _text("job_to_be_done", job_to_be_done),
        "assumptions_broken": assumptions,
        "transformations_used": transformations,
        "mechanism_transfer_ids": transfer_ids,
        "workflow_before": _text("workflow_before", workflow_before),
        "workflow_after": _text("workflow_after", workflow_after),
        "value_creation_chain": _normalize_value_chain(value_creation_chain),
        "value_capture_model": _text("value_capture_model", value_capture_model),
        "automation_thesis": _text("automation_thesis", automation_thesis),
        "defensibility_thesis": _text("defensibility_thesis", defensibility_thesis),
        "compounding_effect": _text("compounding_effect", compounding_effect),
        "critical_dependencies": _unique_text_list(
            "critical_dependencies", critical_dependencies
        ),
        "new_risks": _unique_text_list("new_risks", new_risks),
        "evidence_claim_ids": evidence_refs,
        "unknowns": _unique_text_list("unknowns", unknowns),
        "validation_questions": _unique_text_list(
            "validation_questions", validation_questions
        ),
    }
    candidate = {"candidate_id": _stable_candidate_id(payload), **payload}
    validate_candidate(candidate, graph)
    return candidate


def validate_candidate(candidate: dict[str, Any], graph: dict[str, Any]) -> None:
    """Validate one candidate without granting it scoring or decision authority."""
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_KEYS:
        raise ValueError("candidate keys do not match the PR C contract")
    candidate_id = candidate["candidate_id"]
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise ValueError("candidate_id must be a trusted candidate_<12hex> identifier")
    if candidate["family"] not in CANDIDATE_FAMILIES:
        raise ValueError("invalid candidate family")

    for field in (
        "name",
        "one_sentence_concept",
        "problem_reframe",
        "primary_buyer",
        "user",
        "job_to_be_done",
        "workflow_before",
        "workflow_after",
        "value_capture_model",
        "automation_thesis",
        "defensibility_thesis",
        "compounding_effect",
    ):
        _text(field, candidate[field])

    assumptions = _unique_text_list("assumptions_broken", candidate["assumptions_broken"])
    for assumption_id in assumptions:
        if not _ASSUMPTION_ID_RE.fullmatch(assumption_id):
            raise ValueError("invalid assumption ID")

    transformations = _unique_text_list(
        "transformations_used", candidate["transformations_used"], allow_empty=False
    )
    if set(transformations) - TRANSFORMATIONS:
        raise ValueError("candidate references unknown transformations")

    transfer_ids = _unique_text_list(
        "mechanism_transfer_ids", candidate["mechanism_transfer_ids"]
    )
    for transfer_id in transfer_ids:
        if not _TRANSFER_ID_RE.fullmatch(transfer_id):
            raise ValueError("invalid transfer ID")

    _normalize_value_chain(candidate["value_creation_chain"])
    _unique_text_list("critical_dependencies", candidate["critical_dependencies"])
    _unique_text_list("new_risks", candidate["new_risks"])
    evidence_refs = _unique_text_list("evidence_claim_ids", candidate["evidence_claim_ids"])
    _validate_claim_refs(graph, evidence_refs)
    _unique_text_list("unknowns", candidate["unknowns"])
    _unique_text_list("validation_questions", candidate["validation_questions"])

    trusted_payload = deepcopy(candidate)
    trusted_payload.pop("candidate_id")
    if _stable_candidate_id(trusted_payload) != candidate_id:
        raise ValueError("candidate_id does not match candidate content")


def validate_causal_value_chain(candidate: dict[str, Any]) -> None:
    """Verify that every required link from constraint to value capture is explicit."""
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a dictionary")
    _normalize_value_chain(candidate.get("value_creation_chain"))


def _canonical_dimension_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def audit_candidate_diversity(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect candidate sets that collapse into cosmetic feature/name variants."""
    if not isinstance(candidates, list) or len(candidates) < 2:
        raise ValueError("candidates must contain at least two candidate objects")
    ids: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be a dictionary")
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not _CANDIDATE_ID_RE.fullmatch(candidate_id):
            raise ValueError("each candidate must have a trusted candidate ID")
        ids.append(candidate_id)
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs must be unique")

    qualifying_peers = {candidate_id: 0 for candidate_id in ids}
    pairwise: list[dict[str, Any]] = []
    for left, right in combinations(candidates, 2):
        different_dimensions = [
            dimension
            for dimension in DIVERSITY_DIMENSIONS
            if _canonical_dimension_value(left.get(dimension))
            != _canonical_dimension_value(right.get(dimension))
        ]
        count = len(different_dimensions)
        pairwise.append(
            {
                "left_id": left["candidate_id"],
                "right_id": right["candidate_id"],
                "different_dimensions": different_dimensions,
                "count": count,
            }
        )
        if count >= 3:
            qualifying_peers[left["candidate_id"]] += 1
            qualifying_peers[right["candidate_id"]] += 1

    collapsed = sorted(
        candidate_id
        for candidate_id, peer_count in qualifying_peers.items()
        if peer_count < 2
    )
    return {
        "diversity_ready": not collapsed,
        "pairwise_differences": pairwise,
        "collapsed_candidate_ids": collapsed,
    }


def audit_family_coverage(
    candidates: list[dict[str, Any]],
    non_applicable_families: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Require every canonical candidate family or an explicit non-applicable reason."""
    if not isinstance(candidates, list):
        raise ValueError("candidates must be a list")
    generated: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("family") not in CANDIDATE_FAMILIES:
            raise ValueError("each candidate must contain a canonical family")
        generated.add(candidate["family"])

    non_applicable = non_applicable_families or {}
    if not isinstance(non_applicable, dict):
        raise ValueError("non_applicable_families must be a dictionary")
    normalized_non_applicable: dict[str, str] = {}
    for family, reason in non_applicable.items():
        if family not in CANDIDATE_FAMILIES:
            raise ValueError("non-applicable family must be canonical")
        normalized_non_applicable[family] = _text(
            f"non_applicable_families.{family}", reason
        )
    overlap = sorted(generated & set(normalized_non_applicable))
    if overlap:
        raise ValueError(
            f"families cannot be both generated and non-applicable: {', '.join(overlap)}"
        )
    missing = sorted(CANDIDATE_FAMILIES - generated - set(normalized_non_applicable))
    return {
        "family_ready": not missing,
        "generated_families": sorted(generated),
        "non_applicable_families": dict(sorted(normalized_non_applicable.items())),
        "missing_families": missing,
    }


def create_collision_research_request(
    *,
    candidate_id: str,
    question: str,
    reason: str,
    materiality: str,
    suggested_category: str,
) -> dict[str, str]:
    """Turn an unsupported decision-critical fact into a deterministic research request."""
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID_RE.fullmatch(candidate_id):
        raise ValueError("candidate_id must be a trusted candidate_<12hex> identifier")
    if materiality not in COLLISION_MATERIALITIES:
        raise ValueError(
            f"materiality must be one of {sorted(COLLISION_MATERIALITIES)}"
        )
    if suggested_category not in COLLISION_CATEGORIES:
        raise ValueError(
            f"suggested_category must be one of {sorted(COLLISION_CATEGORIES)}"
        )
    payload = {
        "candidate_id": candidate_id,
        "question": _text("question", question),
        "reason": _text("reason", reason),
        "materiality": materiality,
        "suggested_category": suggested_category,
    }
    return {
        "research_request_id": _stable_hash("collision", payload),
        **payload,
    }
