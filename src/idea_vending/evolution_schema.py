"""E2A extension of the stable v0.3 Evolution State/report contract."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from src.idea_vending import evolution_schema_core as _core
from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evaluator_contract import (
    BLOCKER_KEYS,
    EVALUATION_DIMENSIONS,
    STATUSES as DIMENSION_STATUSES,
)

for _name in dir(_core):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_core, _name)

REALITY_VERDICTS = {"ADVANCE", "REVISE", "HOLD", "REJECT"}
REALITY_ASSESSMENT_KEYS = {
    "candidate_id",
    "family",
    "name",
    "one_sentence_concept",
    "reality_verdict",
    "confidence",
    "strongest_reason_for",
    "strongest_reason_against",
    "dimension_statuses",
    "hard_or_material_blockers",
    "material_unknowns",
    "cheapest_next_validation",
    "evidence_claim_ids",
}
_LEGACY_STATE_KEYS = set(_core._STATE_KEYS)
_STATE_KEYS = _LEGACY_STATE_KEYS | {"candidate_reality_assessments"}
_CANDIDATE_ID_RE = re.compile(r"^candidate_[0-9a-f]{12}$")


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


def _legacy_state(state: dict[str, Any]) -> dict[str, Any]:
    projected = deepcopy(state)
    projected.pop("candidate_reality_assessments", None)
    return projected


def validate_candidate_reality_assessments(
    assessments: Any,
    *,
    registered_evidence_refs: set[str] | None = None,
    require_exact_ten: bool = False,
) -> None:
    if not isinstance(assessments, list):
        raise ValueError("candidate_reality_assessments must be a list")

    candidate_ids: list[str] = []
    families: list[str] = []
    for index, item in enumerate(assessments):
        field = f"candidate_reality_assessments[{index}]"
        if not isinstance(item, dict) or set(item) != REALITY_ASSESSMENT_KEYS:
            raise ValueError(f"{field} keys do not match the E2A contract")
        candidate_id = item["candidate_id"]
        if not isinstance(candidate_id, str) or not _CANDIDATE_ID_RE.fullmatch(candidate_id):
            raise ValueError(f"{field}.candidate_id is invalid")
        if item["family"] not in CANDIDATE_FAMILIES:
            raise ValueError(f"{field}.family is invalid")
        for name in (
            "name",
            "one_sentence_concept",
            "strongest_reason_for",
            "strongest_reason_against",
            "cheapest_next_validation",
        ):
            _text(f"{field}.{name}", item[name])
        if item["reality_verdict"] not in REALITY_VERDICTS:
            raise ValueError(f"{field}.reality_verdict is invalid")
        if item["confidence"] not in _core.CONFIDENCE_LEVELS:
            raise ValueError(f"{field}.confidence is invalid")

        statuses = item["dimension_statuses"]
        if not isinstance(statuses, dict) or set(statuses) != EVALUATION_DIMENSIONS:
            raise ValueError(f"{field}.dimension_statuses must contain all ten dimensions")
        if any(status not in DIMENSION_STATUSES for status in statuses.values()):
            raise ValueError(f"{field}.dimension_statuses contains an invalid status")

        blockers = item["hard_or_material_blockers"]
        if not isinstance(blockers, list):
            raise ValueError(f"{field}.hard_or_material_blockers must be a list")
        blocker_refs: list[str] = []
        for blocker_index, blocker in enumerate(blockers):
            blocker_field = f"{field}.hard_or_material_blockers[{blocker_index}]"
            if not isinstance(blocker, dict) or set(blocker) != BLOCKER_KEYS:
                raise ValueError(f"{blocker_field} keys are invalid")
            _text(f"{blocker_field}.reason", blocker["reason"])
            if blocker["materiality"] not in {"material", "hard"}:
                raise ValueError(f"{blocker_field}.materiality must be material or hard")
            if not isinstance(blocker["resolvable"], bool):
                raise ValueError(f"{blocker_field}.resolvable must be boolean")
            refs = _unique_text_list(
                f"{blocker_field}.evidence_claim_ids", blocker["evidence_claim_ids"]
            )
            if not refs:
                raise ValueError(f"{blocker_field}.evidence_claim_ids must not be empty")
            blocker_refs.extend(refs)

        _unique_text_list(f"{field}.material_unknowns", item["material_unknowns"])
        evidence_refs = _unique_text_list(f"{field}.evidence_claim_ids", item["evidence_claim_ids"])
        if not set(blocker_refs).issubset(set(evidence_refs)):
            raise ValueError(f"{field} blocker evidence must be registered on the assessment")
        if registered_evidence_refs is not None:
            missing = sorted(set(evidence_refs) - registered_evidence_refs)
            if missing:
                raise ValueError(
                    f"{field} evidence references are not registered in state: {', '.join(missing)}"
                )
        candidate_ids.append(candidate_id)
        families.append(item["family"])

    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate_reality_assessments candidate IDs must be unique")
    if len(families) != len(set(families)):
        raise ValueError("candidate_reality_assessments families must be unique")
    if require_exact_ten:
        if len(assessments) != 10:
            raise ValueError("complete report requires exactly ten candidate reality assessments")
        if set(families) != CANDIDATE_FAMILIES:
            raise ValueError("complete report must contain every canonical candidate family exactly once")


def create_evolution_state(raw_idea: str, evolution_id: str) -> dict[str, Any]:
    state = _core.create_evolution_state(raw_idea, evolution_id)
    state["candidate_reality_assessments"] = []
    validate_evolution_state(state)
    return state


def validate_evolution_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be a dictionary")
    if set(state) != _STATE_KEYS:
        raise ValueError("state keys do not match the v0.3 E2A contract")
    _core.validate_evolution_state(_legacy_state(state))
    validate_candidate_reality_assessments(state["candidate_reality_assessments"])


def validate_complete_report(state: dict[str, Any]) -> None:
    validate_evolution_state(state)
    _core.validate_complete_report(_legacy_state(state))
    validate_candidate_reality_assessments(
        state["candidate_reality_assessments"],
        registered_evidence_refs=set(state["evidence_refs"]),
        require_exact_ten=True,
    )
