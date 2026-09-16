"""Guarded handoff from a completed v0.3 decision into the v0.2 package generator."""

from __future__ import annotations

from typing import Any

from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.evolution_schema import validate_complete_report
from src.idea_vending.package_generator import generate_development_package


def _resolve_handoff_idea(state: dict[str, Any]) -> str:
    validate_complete_report(state)

    decision = state["decision"]
    if decision in {"HOLD", "KILL"}:
        raise ValueError(f"{decision} decision blocks development handoff")
    if state["human_decision"] != "proceed":
        raise ValueError("explicit human proceed approval is required for development handoff")

    evolved_idea = state["evolved_idea"]
    if decision == "MODIFY":
        if not isinstance(evolved_idea, str) or not evolved_idea.strip():
            raise ValueError("evolved_idea is required for MODIFY handoff")
        return evolved_idea

    if decision == "GO":
        if isinstance(evolved_idea, str) and evolved_idea.strip():
            return evolved_idea
        return state["raw_idea"]

    raise ValueError("only GO or MODIFY decisions can enter development handoff")


def can_handoff_to_development(state: dict[str, Any]) -> bool:
    """Return True only when a complete report and explicit human approval permit handoff."""
    try:
        _resolve_handoff_idea(state)
    except ValueError:
        return False
    return True


def generate_approved_development_package(state: dict[str, Any]) -> dict[str, str]:
    """Generate the existing v0.2 package only after v0.3 decision gates pass."""
    handoff_idea = _resolve_handoff_idea(state)
    analysis = analyze_idea(handoff_idea)
    return generate_development_package(handoff_idea, analysis)
