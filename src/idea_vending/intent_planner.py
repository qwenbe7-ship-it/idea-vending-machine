"""Provider-neutral intent interpretation and bounded research planning.

This module produces requests only. Model output remains untrusted until the
Intent Model or Research Plan validators accept it. Research planning generates
questions, never evidence or official decisions.
"""

from __future__ import annotations

from typing import Any

from src.idea_vending.ideation_contract import create_ideation_request
from src.idea_vending.intent_model import intent_model_schema, validate_intent_model


RESEARCH_PLAN_CATEGORIES = (
    "market_customer_demand",
    "workflow_economics",
    "alternatives_incumbents",
    "implementation_feasibility",
    "data_quality",
    "regulation_security",
    "failure_blockers",
    "adjacent_mechanisms",
)


def _question_array_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
        "minItems": 1,
        "uniqueItems": True,
    }


def research_plan_schema() -> dict[str, Any]:
    """Return the exact bounded research-question contract."""
    questions = {
        category: _question_array_schema() for category in RESEARCH_PLAN_CATEGORIES
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["research_questions"],
        "properties": {
            "research_questions": {
                "type": "object",
                "additionalProperties": False,
                "required": list(RESEARCH_PLAN_CATEGORIES),
                "properties": questions,
            }
        },
    }


def _normalize_questions(category: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"research plan category {category} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(
            f"research plan category {category} must contain only non-empty strings"
        )
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"research plan category {category} must not contain duplicates")
    return normalized


def validate_research_plan(value: Any) -> dict[str, Any]:
    """Validate a question-only plan with exactly the canonical categories."""
    if not isinstance(value, dict) or set(value) != {"research_questions"}:
        raise ValueError("research plan keys do not match the contract")
    questions = value["research_questions"]
    if not isinstance(questions, dict) or set(questions) != set(RESEARCH_PLAN_CATEGORIES):
        raise ValueError("research plan categories do not match the contract")
    return {
        "research_questions": {
            category: _normalize_questions(category, questions[category])
            for category in RESEARCH_PLAN_CATEGORIES
        }
    }


def build_intent_request(raw_idea: str) -> dict[str, Any]:
    """Build the first provider-neutral interpretation request."""
    if not isinstance(raw_idea, str) or not raw_idea.strip():
        raise ValueError("raw_idea must be a non-empty string")
    return create_ideation_request(
        operation="interpret_intent",
        objective=(
            "Interpret the user's real objective, desired outcome, actors, constraints, "
            "success conditions, non-goals, automation target, and unresolved facts."
        ),
        raw_idea=raw_idea,
        problem_context={},
        assumption_context=[],
        evidence_summary=[],
        allowed_transformations=[],
        required_output_schema=intent_model_schema(),
        constraints=[
            "Do not invent missing user facts; preserve them as material_unknowns.",
            "Keep contradictory requirements explicit instead of silently reconciling them.",
            "Do not create evidence, trusted IDs, rankings, scores, or official decisions.",
        ],
    )


def build_research_plan_request(intent_model: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded question-generation request from validated intent.

    The legacy provider-neutral envelope requires a non-empty ``raw_idea`` field.
    At this post-interpretation stage the canonical primary objective is used as
    that source text; the full validated Intent Model remains available under
    ``problem_context.intent_model`` and is the authoritative planning context.
    """
    intent = validate_intent_model(intent_model)
    return create_ideation_request(
        operation="plan_research",
        objective=(
            "Create a bounded evidence-question plan that resolves the user's objective, "
            "constraints, success metrics, risks, and material unknowns before solutions are forged."
        ),
        raw_idea=intent["primary_objective"],
        problem_context={"intent_model": intent},
        assumption_context=[],
        evidence_summary=[],
        allowed_transformations=[],
        required_output_schema=research_plan_schema(),
        constraints=[
            "Return questions only; do not create, cite, or claim evidence in this planning step.",
            "Cover every required research category exactly once as a question group.",
            "Drive questions from hard constraints, success metrics, evidence questions, and material unknowns.",
            "Do not rank solutions or set official decisions.",
        ],
    )


def flatten_research_questions(
    research_plan: dict[str, Any],
    *,
    categories: tuple[str, ...] | None = None,
) -> list[str]:
    """Return deterministic de-duplicated questions for downstream research requests."""
    plan = validate_research_plan(research_plan)
    selected = RESEARCH_PLAN_CATEGORIES if categories is None else categories
    unknown = set(selected) - set(RESEARCH_PLAN_CATEGORIES)
    if unknown:
        raise ValueError(f"unknown research plan categories: {sorted(unknown)}")
    flattened: list[str] = []
    for category in selected:
        for question in plan["research_questions"][category]:
            if question not in flattened:
                flattened.append(question)
    return flattened
