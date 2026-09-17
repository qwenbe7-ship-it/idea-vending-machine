"""Explicit, uncertainty-preserving Intent Model contract.

The Intent Model is a structured interpretation boundary between a user's raw
idea and later research/Forge stages. It must never manufacture missing user
facts: fields that can legitimately be unknown remain ``None`` or empty and the
uncertainty stays explicit in ``material_unknowns``.
"""

from __future__ import annotations

from typing import Any


INTENT_MODEL_FIELDS = (
    "primary_objective",
    "desired_outcome",
    "primary_buyer",
    "primary_user",
    "jobs_to_be_done",
    "hard_constraints",
    "soft_preferences",
    "success_metrics",
    "non_goals",
    "risk_tolerance",
    "automation_target",
    "evidence_questions",
    "material_unknowns",
    "interpretation_notes",
)
INTENT_MODEL_KEYS = set(INTENT_MODEL_FIELDS)

_REQUIRED_TEXT_FIELDS = (
    "primary_objective",
    "desired_outcome",
)
_NULLABLE_TEXT_FIELDS = (
    "primary_buyer",
    "primary_user",
    "risk_tolerance",
    "automation_target",
)
_LIST_FIELDS = (
    "jobs_to_be_done",
    "hard_constraints",
    "soft_preferences",
    "success_metrics",
    "non_goals",
    "evidence_questions",
    "material_unknowns",
    "interpretation_notes",
)


def _required_text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _nullable_text(field: str, value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be null or a non-empty string")
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


def _string_list_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
        "uniqueItems": True,
    }


def intent_model_schema() -> dict[str, Any]:
    """Return the canonical machine-readable Intent Model schema."""
    properties: dict[str, Any] = {
        field: {"type": "string", "minLength": 1}
        for field in _REQUIRED_TEXT_FIELDS
    }
    properties.update(
        {
            field: {"type": ["string", "null"], "minLength": 1}
            for field in _NULLABLE_TEXT_FIELDS
        }
    )
    properties.update({field: _string_list_schema() for field in _LIST_FIELDS})
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(INTENT_MODEL_FIELDS),
        "properties": properties,
    }


def validate_intent_model(value: Any) -> dict[str, Any]:
    """Validate and normalize an Intent Model without filling unknown facts."""
    if not isinstance(value, dict) or set(value) != INTENT_MODEL_KEYS:
        raise ValueError("intent model keys do not match the contract")

    normalized: dict[str, Any] = {}
    for field in _REQUIRED_TEXT_FIELDS:
        normalized[field] = _required_text(field, value[field])
    for field in _NULLABLE_TEXT_FIELDS:
        normalized[field] = _nullable_text(field, value[field])
    for field in _LIST_FIELDS:
        normalized[field] = _unique_text_list(field, value[field])

    return {field: normalized[field] for field in INTENT_MODEL_FIELDS}
