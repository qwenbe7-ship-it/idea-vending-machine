"""Deterministic Markdown package generator for Idea Vending Machine v0.2."""

from __future__ import annotations

import hashlib
from typing import Any

_REQUIRED_ANALYSIS_KEYS = {
    "problem",
    "customer",
    "automation_level",
    "feasibility_level",
    "risks",
    "mvp_scope",
    "acceptance_criteria",
}


def _normalized_idea(idea: str) -> str:
    if not isinstance(idea, str):
        raise ValueError("idea must be a string")
    normalized = " ".join(idea.split())
    if not normalized:
        raise ValueError("idea must not be empty")
    return normalized


def _validate_analysis(analysis: dict[str, Any]) -> None:
    if not isinstance(analysis, dict):
        raise ValueError("analysis must be a dictionary")
    missing = sorted(_REQUIRED_ANALYSIS_KEYS - set(analysis))
    if missing:
        raise ValueError(f"analysis missing required fields: {', '.join(missing)}")
    for key in ("risks", "mvp_scope", "acceptance_criteria"):
        value = analysis[key]
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"analysis field {key} must be a non-empty string list")


def _project_id(idea: str) -> str:
    digest = hashlib.sha256(idea.encode("utf-8")).hexdigest()[:12]
    return f"ivm-{digest}"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _build_spec(idea: str, analysis: dict[str, Any], project_id: str) -> str:
    return f"""# Product Specification

Project ID: `{project_id}`

## Original Idea

{idea}

## Problem

{analysis['problem']}

## Target Customer

{analysis['customer']}

## Agent MD Assessment

- Automation level: **{analysis['automation_level']}**
- Feasibility level: **{analysis['feasibility_level']}**

## MVP Scope

{_bullets(analysis['mvp_scope'])}

## Risks and Human Approval

{_bullets(analysis['risks'])}

High-risk or uncertain outputs must be distinguishable from verified success and must remain reviewable by a human operator.

## Acceptance Criteria

{_bullets(analysis['acceptance_criteria'])}

## Out of Scope

- SaaS billing or subscription management
- User authentication unless a later specification explicitly requires it
- Automatic production deployment
- Autonomous high-risk decisions without human review
- Technology choices that are not justified by validated requirements
"""


def _build_design(idea: str, analysis: dict[str, Any], project_id: str) -> str:
    criteria = _numbered(analysis["acceptance_criteria"])
    return f"""# System Design

Project ID: `{project_id}`

## Design Intent

Build the smallest verifiable system for this idea: {idea}

## Architecture Responsibilities

1. **Input boundary** — accept the minimum required user input and reject malformed or incomplete input explicitly.
2. **Processing boundary** — transform input into structured data and isolate probabilistic judgement from deterministic rules.
3. **Verification boundary** — validate required fields, uncertainty states, and business rules before success is returned.
4. **Output boundary** — return a human-reviewable result with enough evidence to understand what happened.

## Data Flow

`Input → validation → structured processing → deterministic checks → result + evidence`

## AI vs Deterministic Logic

AI judgement, if introduced later, is limited to tasks that genuinely require interpretation. Required fields, validation rules, failure states, release gates, and acceptance checks remain deterministic wherever practical.

## Failure and Uncertainty Handling

- Invalid or insufficient input returns a clear failure state instead of a guessed result.
- Uncertain judgement remains distinguishable from verified output.
- External dependency failures must not be reported as successful processing.
- High-risk decisions require human confirmation before consequential action.

## Security and Data Minimization

- Collect only data required by the MVP scope.
- Avoid persisting sensitive input unless persistence is explicitly required.
- Keep credentials and secrets outside generated source and logs.
- Treat uploaded or user-provided content as untrusted input.

## Verification Strategy

The implementation is releasable only when these acceptance criteria are demonstrated by automated or repeatable checks:

{criteria}
"""


def _build_plan(idea: str, analysis: dict[str, Any], project_id: str) -> str:
    task_sections = []
    for index, responsibility in enumerate(analysis["mvp_scope"], start=1):
        task_sections.append(
            f"""### Task {index}: MVP responsibility

**Responsibility:** {responsibility}

**Completion condition:** A focused automated or repeatable test demonstrates this responsibility while preserving explicit failure states.
"""
        )
    gate_number = len(task_sections) + 1
    task_sections.append(
        f"""### Task {gate_number}: Production Gate

**Responsibility:** Verify the full MVP against every acceptance criterion before release.

**Completion condition:** The complete test/verification command exits successfully, every acceptance criterion has evidence, and any failed check blocks release.
"""
    )
    criteria = _bullets(analysis["acceptance_criteria"])
    return f"""# Implementation Plan

Project ID: `{project_id}`

## Goal

Implement the smallest testable version of: {idea}

## Delivery Rules

- Build one responsibility at a time.
- Define a failing test or measurable check before production behavior.
- Keep uncertain AI judgement separate from deterministic acceptance rules.
- Do not mark work complete without fresh verification evidence.

{"\n".join(task_sections)}
## Final Release Criteria

{criteria}
"""


def generate_development_package(idea: str, analysis: dict[str, Any]) -> dict[str, str]:
    """Return deterministic Markdown documents for a validated idea analysis."""
    normalized = _normalized_idea(idea)
    _validate_analysis(analysis)
    project_id = _project_id(normalized)
    documents = {
        "spec.md": _build_spec(normalized, analysis, project_id),
        "design.md": _build_design(normalized, analysis, project_id),
        "plan.md": _build_plan(normalized, analysis, project_id),
    }
    for filename, content in documents.items():
        upper = content.upper()
        if "TBD" in upper or "TODO" in upper:
            raise ValueError(f"generated placeholder marker in {filename}")
    return documents
