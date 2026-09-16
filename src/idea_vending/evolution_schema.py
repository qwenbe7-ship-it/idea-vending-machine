"""Deterministic state and report contracts for Idea Vending Machine v0.3."""

from __future__ import annotations

import re
from typing import Any

DECISIONS = {"GO", "MODIFY", "HOLD", "KILL"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
HUMAN_DECISIONS = {"proceed", "refine", "hold", "kill"}
REPORT_STATUSES = {"draft", "complete"}

DETAIL_SECTION_KEYS = {
    "original_idea_intent",
    "underlying_problem",
    "market_definition",
    "global_market_status",
    "market_size_forecast",
    "competitive_landscape",
    "customer_economics",
    "assumption_map",
    "assumption_destruction",
    "cross_industry_transfer",
    "candidate_forge",
    "candidate_critique",
    "evolution_delta",
    "evidence_for",
    "evidence_against",
    "agent_md_gate",
    "risk_register",
    "what_must_be_true",
    "validation_plan",
    "final_decision",
}

_EXECUTIVE_BRIEF_KEYS = {
    "thesis",
    "why_now",
    "evolution_delta",
    "market_snapshot",
    "best_customer",
    "business_value",
    "reasons_for",
    "reasons_against",
    "critical_unknowns",
    "cheapest_next_validation",
    "evidence_refs",
}
_MARKET_SNAPSHOT_KEYS = {"stage", "current_market", "forecast_market", "growth", "buyer"}
_VALIDATION_KEYS = {"action", "pass_condition", "fail_condition"}

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


def _require_non_empty_text(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _validate_string_list(field: str, value: Any, *, exact_length: int | None = None, min_length: int = 0) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    if exact_length is not None and len(value) != exact_length:
        raise ValueError(f"{field} must contain exactly {exact_length} items")
    if len(value) < min_length:
        raise ValueError(f"{field} must contain at least {min_length} items")


def _validate_evidence_refs(field: str, refs: Any) -> None:
    _validate_string_list(field, refs)


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

    _validate_evidence_refs("evidence_refs", state["evidence_refs"])


def _validate_market_entries(field: str, entries: Any) -> None:
    if not isinstance(entries, list):
        raise ValueError(f"{field} must be a list")
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"{field}[{index}] must be an object")
        _require_non_empty_text(f"{field}[{index}].label", item.get("label"))
        _validate_evidence_refs(f"{field}[{index}].evidence_refs", item.get("evidence_refs"))


def validate_executive_brief(brief: dict[str, Any]) -> None:
    """Validate the three-minute executive summary contract."""
    if not isinstance(brief, dict) or set(brief) != _EXECUTIVE_BRIEF_KEYS:
        raise ValueError("executive_brief keys do not match the v0.3 contract")

    for field in ("thesis", "why_now", "evolution_delta", "best_customer", "business_value"):
        _require_non_empty_text(field, brief[field])

    _validate_string_list("reasons_for", brief["reasons_for"], exact_length=3)
    _validate_string_list("reasons_against", brief["reasons_against"], exact_length=3)
    _validate_string_list("critical_unknowns", brief["critical_unknowns"], min_length=1)
    _validate_evidence_refs("executive_brief.evidence_refs", brief["evidence_refs"])

    market = brief["market_snapshot"]
    if not isinstance(market, dict) or set(market) != _MARKET_SNAPSHOT_KEYS:
        raise ValueError("market_snapshot keys do not match the v0.3 contract")
    _require_non_empty_text("market_snapshot.stage", market["stage"])
    _require_non_empty_text("market_snapshot.buyer", market["buyer"])
    _validate_market_entries("market_snapshot.current_market", market["current_market"])
    _validate_market_entries("market_snapshot.forecast_market", market["forecast_market"])
    _validate_market_entries("market_snapshot.growth", market["growth"])

    validation = brief["cheapest_next_validation"]
    if not isinstance(validation, dict) or set(validation) != _VALIDATION_KEYS:
        raise ValueError("cheapest_next_validation keys do not match the v0.3 contract")
    for field in _VALIDATION_KEYS:
        _require_non_empty_text(f"cheapest_next_validation.{field}", validation[field])


def validate_detailed_analysis(details: dict[str, Any]) -> None:
    """Validate the canonical evidence-and-analysis section set."""
    if not isinstance(details, dict) or set(details) != DETAIL_SECTION_KEYS:
        raise ValueError("detailed_analysis must contain every canonical v0.3 section")
    for section_name, section in details.items():
        if not isinstance(section, dict):
            raise ValueError(f"detailed_analysis.{section_name} must be an object")
        _require_non_empty_text(f"detailed_analysis.{section_name}.summary", section.get("summary"))
        _validate_evidence_refs(
            f"detailed_analysis.{section_name}.evidence_refs",
            section.get("evidence_refs"),
        )


def _collect_report_evidence_refs(state: dict[str, Any]) -> set[str]:
    brief = state["executive_brief"]
    refs = set(brief["evidence_refs"])
    market = brief["market_snapshot"]
    for field in ("current_market", "forecast_market", "growth"):
        for entry in market[field]:
            refs.update(entry["evidence_refs"])
    for section in state["detailed_analysis"].values():
        refs.update(section["evidence_refs"])
    return refs


def validate_complete_report(state: dict[str, Any]) -> None:
    """Validate a complete report and guarantee evidence-ref traceability."""
    validate_evolution_state(state)
    if state["report_status"] != "complete":
        raise ValueError("report_status must be complete")
    if state["decision"] is None:
        raise ValueError("decision is required for a complete report")
    if state["confidence"] is None:
        raise ValueError("confidence is required for a complete report")
    if state["executive_brief"] is None:
        raise ValueError("executive_brief is required for a complete report")
    if state["detailed_analysis"] is None:
        raise ValueError("detailed_analysis is required for a complete report")

    validate_executive_brief(state["executive_brief"])
    validate_detailed_analysis(state["detailed_analysis"])

    registered = set(state["evidence_refs"])
    referenced = _collect_report_evidence_refs(state)
    missing = sorted(referenced - registered)
    if missing:
        raise ValueError(f"evidence references are not registered in state: {', '.join(missing)}")
