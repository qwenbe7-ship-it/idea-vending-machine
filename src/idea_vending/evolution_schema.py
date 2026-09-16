"""Deterministic state and report contracts for Idea Vending Machine v0.3."""

from __future__ import annotations

import re
from typing import Any

DECISIONS = {"GO", "MODIFY", "HOLD", "KILL"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
HUMAN_DECISIONS = {"proceed", "refine", "hold", "kill"}
REPORT_STATUSES = {"draft", "complete"}

_EVOLUTION_ID_RE = re.compile(r"^evo_[A-Za-z0-9_-]{8,64}$")
_STATE_KEYS = {
    "evolution_id",
    "raw_idea",
    "normalized_intent",
    "evolved_idea",
    "report_status",
    "decision",
    "confidence",
    "human_decision",
    "selected_concept_id",
    "executive_brief",
    "detailed_analysis",
    "evidence_refs",
}


def create_evolution_state(raw_idea: str, evolution_id: str) -> dict[str, Any]:
    """Create an empty v0.3 state while preserving the original idea verbatim."""
    if not isinstance(raw_idea, str) or not raw_idea.strip():
        raise ValueError("raw_idea must be a non-empty string")
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")

    state = {
        "evolution_id": evolution_id,
        "raw_idea": raw_idea,
        "normalized_intent": None,
        "evolved_idea": None,
        "report_status": "draft",
        "decision": None,
        "confidence": None,
        "human_decision": None,
        "selected_concept_id": None,
        "executive_brief": None,
        "detailed_analysis": None,
        "evidence_refs": [],
    }
    validate_evolution_state(state)
    return state


def _validate_optional_choice(field: str, value: Any, allowed: set[str]) -> None:
    if value is not None and value not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)} or null")


def validate_evolution_state(state: dict[str, Any]) -> None:
    """Validate the stable PR-A evolution-state envelope."""
    if not isinstance(state, dict):
        raise ValueError("state must be a dictionary")
    if set(state) != _STATE_KEYS:
        raise ValueError("state keys do not match the v0.3 contract")

    evolution_id = state["evolution_id"]
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")

    raw_idea = state["raw_idea"]
    if not isinstance(raw_idea, str) or not raw_idea.strip():
        raise ValueError("raw_idea must be a non-empty string")

    if state["report_status"] not in REPORT_STATUSES:
        raise ValueError(f"report_status must be one of {sorted(REPORT_STATUSES)}")
    _validate_optional_choice("decision", state["decision"], DECISIONS)
    _validate_optional_choice("confidence", state["confidence"], CONFIDENCE_LEVELS)
    _validate_optional_choice("human_decision", state["human_decision"], HUMAN_DECISIONS)

    for field in ("normalized_intent", "evolved_idea", "selected_concept_id"):
        value = state[field]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field} must be a non-empty string or null")

    if state["executive_brief"] is not None and not isinstance(state["executive_brief"], dict):
        raise ValueError("executive_brief must be a dictionary or null")
    if state["detailed_analysis"] is not None and not isinstance(state["detailed_analysis"], dict):
        raise ValueError("detailed_analysis must be a dictionary or null")

    refs = state["evidence_refs"]
    if not isinstance(refs, list) or not all(isinstance(ref, str) and ref.strip() for ref in refs):
        raise ValueError("evidence_refs must be a list of non-empty strings")
