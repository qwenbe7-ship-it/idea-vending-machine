"""Provider-neutral ideation boundary for Idea Vending Machine v0.3 PR C.

Provider output is always untrusted structured data. This module does not assign
trusted IDs, mutate Evolution State, or make business decisions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from src.idea_vending.reframing import TRANSFORMATIONS

IDEATION_OPERATIONS = {
    "extract_assumptions",
    "challenge_assumptions",
    "propose_reframes",
    "discover_mechanisms",
    "forge_candidates",
}

_REQUEST_KEYS = {
    "operation",
    "objective",
    "raw_idea",
    "problem_context",
    "assumption_context",
    "evidence_summary",
    "allowed_transformations",
    "required_output_schema",
    "constraints",
}


class IdeationProvider(Protocol):
    """Minimal provider interface; implementations may use any model vendor."""

    def generate(self, request: dict[str, Any]) -> dict[str, Any]: ...


def _require_text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_string_list(field: str, value: Any, *, allow_empty: bool = True) -> list[str]:
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


def validate_ideation_request(request: dict[str, Any]) -> None:
    """Validate the stable provider-neutral request envelope."""
    if not isinstance(request, dict) or set(request) != _REQUEST_KEYS:
        raise ValueError("ideation request keys do not match the PR C contract")
    if request["operation"] not in IDEATION_OPERATIONS:
        raise ValueError(f"operation must be one of {sorted(IDEATION_OPERATIONS)}")
    _require_text("objective", request["objective"])
    _require_text("raw_idea", request["raw_idea"])
    if not isinstance(request["problem_context"], dict):
        raise ValueError("problem_context must be a dictionary")
    if not isinstance(request["assumption_context"], list) or not all(
        isinstance(item, dict) for item in request["assumption_context"]
    ):
        raise ValueError("assumption_context must be a list of dictionaries")
    if not isinstance(request["evidence_summary"], list) or not all(
        isinstance(item, dict) for item in request["evidence_summary"]
    ):
        raise ValueError("evidence_summary must be a list of dictionaries")
    transformations = _require_string_list(
        "allowed_transformations", request["allowed_transformations"]
    )
    invalid = sorted(set(transformations) - TRANSFORMATIONS)
    if invalid:
        raise ValueError(f"unknown transformations: {', '.join(invalid)}")
    if not isinstance(request["required_output_schema"], dict):
        raise ValueError("required_output_schema must be a dictionary")
    _require_string_list("constraints", request["constraints"], allow_empty=False)


def create_ideation_request(
    *,
    operation: str,
    objective: str,
    raw_idea: str,
    problem_context: dict[str, Any],
    assumption_context: list[dict[str, Any]],
    evidence_summary: list[dict[str, Any]],
    allowed_transformations: list[str],
    required_output_schema: dict[str, Any],
    constraints: list[str],
) -> dict[str, Any]:
    """Build a defensive request for an injected ideation provider."""
    request = {
        "operation": operation,
        "objective": objective,
        "raw_idea": raw_idea,
        "problem_context": deepcopy(problem_context),
        "assumption_context": deepcopy(assumption_context),
        "evidence_summary": deepcopy(evidence_summary),
        "allowed_transformations": list(allowed_transformations),
        "required_output_schema": deepcopy(required_output_schema),
        "constraints": list(constraints),
    }
    validate_ideation_request(request)
    return request


def run_ideation_operation(
    provider: IdeationProvider, request: dict[str, Any]
) -> dict[str, Any]:
    """Execute a provider call without granting the provider trusted-state authority."""
    validate_ideation_request(request)
    if not hasattr(provider, "generate") or not callable(provider.generate):
        raise ValueError("provider must expose a callable generate(request) method")
    provider_request = deepcopy(request)
    result = provider.generate(provider_request)
    if not isinstance(result, dict):
        raise ValueError("provider output must be a dictionary")
    return deepcopy(result)
