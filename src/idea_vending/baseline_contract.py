"""Deterministic raw-idea baseline contract for Idea Vending Machine v0.3 PR D."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

BASELINE_KEYS = {
    "baseline_id",
    "evolution_id",
    "raw_idea",
    "problem_framing",
    "primary_buyer",
    "user",
    "workflow",
    "value_capture_hypothesis",
    "automation_thesis",
    "critical_dependencies",
    "risks",
    "evidence_claim_ids",
    "unknowns",
    "validation_questions",
}

_EVOLUTION_ID_RE = re.compile(r"^evo_[A-Za-z0-9_-]{8,64}$")
_BASELINE_ID_RE = re.compile(r"^baseline_[0-9a-f]{12}$")


def _text(field: str, value: Any, *, preserve: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value if preserve else value.strip()


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


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"baseline_{hashlib.sha256(raw).hexdigest()[:12]}"


def create_baseline(
    *,
    graph: dict[str, Any],
    evolution_id: str,
    raw_idea: str,
    problem_framing: str,
    primary_buyer: str,
    user: str,
    workflow: str,
    value_capture_hypothesis: str,
    automation_thesis: str,
    critical_dependencies: list[str],
    risks: list[str],
    evidence_claim_ids: list[str],
    unknowns: list[str],
    validation_questions: list[str],
) -> dict[str, Any]:
    """Create the immutable comparison baseline for the user's original idea."""
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")
    if graph.get("evolution_id") != evolution_id:
        raise ValueError("graph evolution_id must match baseline evolution_id")

    payload = {
        "evolution_id": evolution_id,
        "raw_idea": _text("raw_idea", raw_idea, preserve=True),
        "problem_framing": _text("problem_framing", problem_framing),
        "primary_buyer": _text("primary_buyer", primary_buyer),
        "user": _text("user", user),
        "workflow": _text("workflow", workflow),
        "value_capture_hypothesis": _text(
            "value_capture_hypothesis", value_capture_hypothesis
        ),
        "automation_thesis": _text("automation_thesis", automation_thesis),
        "critical_dependencies": _unique_text_list(
            "critical_dependencies", critical_dependencies
        ),
        "risks": _unique_text_list("risks", risks),
        "evidence_claim_ids": _unique_text_list(
            "evidence_claim_ids", evidence_claim_ids
        ),
        "unknowns": _unique_text_list("unknowns", unknowns),
        "validation_questions": _unique_text_list(
            "validation_questions", validation_questions
        ),
    }
    unknown_claims = sorted(set(payload["evidence_claim_ids"]) - _known_claim_ids(graph))
    if unknown_claims:
        raise ValueError(
            f"unknown Evidence Graph claim IDs: {', '.join(unknown_claims)}"
        )
    if not payload["unknowns"] and not payload["validation_questions"]:
        raise ValueError("unknowns or validation_questions must remain explicit")

    baseline = {"baseline_id": _stable_id(payload), **payload}
    validate_baseline(baseline, graph)
    return baseline


def validate_baseline(baseline: dict[str, Any], graph: dict[str, Any]) -> None:
    """Validate baseline structure, evidence references, and content-addressed identity."""
    if not isinstance(baseline, dict) or set(baseline) != BASELINE_KEYS:
        raise ValueError("baseline keys do not match the PR D contract")
    baseline_id = baseline["baseline_id"]
    if not isinstance(baseline_id, str) or not _BASELINE_ID_RE.fullmatch(baseline_id):
        raise ValueError("baseline_id must be baseline_<12hex>")
    evolution_id = baseline["evolution_id"]
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")
    if graph.get("evolution_id") != evolution_id:
        raise ValueError("graph evolution_id must match baseline evolution_id")

    _text("raw_idea", baseline["raw_idea"], preserve=True)
    for field in (
        "problem_framing",
        "primary_buyer",
        "user",
        "workflow",
        "value_capture_hypothesis",
        "automation_thesis",
    ):
        _text(field, baseline[field])
    for field in (
        "critical_dependencies",
        "risks",
        "evidence_claim_ids",
        "unknowns",
        "validation_questions",
    ):
        _unique_text_list(field, baseline[field])
    if not baseline["unknowns"] and not baseline["validation_questions"]:
        raise ValueError("unknowns or validation_questions must remain explicit")

    unknown_claims = sorted(
        set(baseline["evidence_claim_ids"]) - _known_claim_ids(graph)
    )
    if unknown_claims:
        raise ValueError(
            f"unknown Evidence Graph claim IDs: {', '.join(unknown_claims)}"
        )

    payload = deepcopy(baseline)
    payload.pop("baseline_id")
    if _stable_id(payload) != baseline_id:
        raise ValueError("baseline_id does not match baseline content")
