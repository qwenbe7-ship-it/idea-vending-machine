"""End-to-end provider-backed evolution runtime for Idea Vending Machine v0.3 PR E1."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable

from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.baseline_contract import create_baseline
from src.idea_vending.candidate_forge import audit_candidate_set, create_candidate
from src.idea_vending.decision_engine import (
    apply_decision_to_state,
    classify_option,
    decide_evolution,
    derive_confidence,
)
from src.idea_vending.evidence_attachment import (
    attach_evidence_refs,
    validate_state_evidence_against_graph,
)
from src.idea_vending.evidence_graph import audit_evidence_coverage, create_evidence_graph
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.evolution_schema import (
    DETAIL_SECTION_KEYS,
    create_evolution_state,
    validate_complete_report,
    validate_evolution_state,
)
from src.idea_vending.ideation_contract import create_ideation_request, run_ideation_operation
from src.idea_vending.independent_evaluator import (
    build_evaluation_request,
    ingest_evaluator_output,
)
from src.idea_vending.mechanism_transfer import create_mechanism_transfer
from src.idea_vending.openai_provider import ProviderSchemaMismatch
from src.idea_vending.provider_transport import (
    ProviderAuthFailed,
    ProviderPermissionDenied,
    ProviderHTTPError,
    ProviderInvalidJSON,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderResponseTooLarge,
    ProviderTimeout,
)
from src.idea_vending.reframing import (
    TRANSFORMATIONS,
    create_assumption,
    create_assumption_challenge,
    create_transformation_test,
)
from src.idea_vending.research_engine import (
    complete_research_pass,
    create_research_request,
    ingest_provider_result,
)
from src.idea_vending.runtime_schema import (
    append_stage_event,
    create_runtime_record,
    mark_runtime_completed,
    mark_runtime_failed,
    mark_runtime_incomplete,
    record_provider_run,
)

_PROVIDER_FAILURES = {
    ProviderNotConfigured: "provider_not_configured",
    ProviderAuthFailed: "provider_auth_failed",
    ProviderPermissionDenied: "provider_permission_denied",
    ProviderRateLimited: "provider_rate_limited",
    ProviderTimeout: "provider_timeout",
    ProviderHTTPError: "provider_http_error",
    ProviderInvalidJSON: "provider_invalid_json",
    ProviderResponseTooLarge: "provider_http_error",
    ProviderSchemaMismatch: "provider_schema_mismatch",
}


def _digest(prefix: str, value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:16]}"


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _text_array() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _assumption_schema() -> dict[str, Any]:
    item = _schema(
        {
            "statement": {"type": "string"},
            "assumption_type": {"type": "string"},
            "scope": {"type": "string"},
            "why_it_exists": {"type": "string"},
            "supporting_claim_ids": _text_array(),
            "contradicting_claim_ids": _text_array(),
            "status": {"type": "string"},
        },
        [
            "statement",
            "assumption_type",
            "scope",
            "why_it_exists",
            "supporting_claim_ids",
            "contradicting_claim_ids",
            "status",
        ],
    )
    return _schema({"assumptions": {"type": "array", "items": item}}, ["assumptions"])


def _challenge_schema() -> dict[str, Any]:
    item = _schema(
        {
            "assumption_index": {"type": "integer"},
            "challenge_question": {"type": "string"},
            "remove_or_invert_test": {"type": "string"},
            "expected_effect_if_false": {"type": "string"},
            "new_opportunity_if_false": {"type": "string"},
            "new_risk_if_false": {"type": "string"},
        },
        [
            "assumption_index",
            "challenge_question",
            "remove_or_invert_test",
            "expected_effect_if_false",
            "new_opportunity_if_false",
            "new_risk_if_false",
        ],
    )
    return _schema({"challenges": {"type": "array", "items": item}}, ["challenges"])


def _transformation_schema() -> dict[str, Any]:
    item = _schema(
        {
            "transformation": {"type": "string"},
            "applicable": {"type": "boolean"},
            "reason": {"type": "string"},
            "resulting_reframe": {"type": "string"},
            "materiality": {"type": "string"},
        },
        ["transformation", "applicable", "reason", "resulting_reframe", "materiality"],
    )
    return _schema(
        {"transformations": {"type": "array", "items": item}}, ["transformations"]
    )


def _mechanism_schema() -> dict[str, Any]:
    fields = [
        "source_domain",
        "mechanism_name",
        "mechanism_description",
        "source_constraint",
        "why_it_works_there",
        "target_equivalent_constraint",
        "transfer_logic",
        "value_chain_change",
        "expected_customer_value",
    ]
    properties = {field: {"type": "string"} for field in fields}
    properties.update({"new_risks": _text_array(), "supporting_claim_ids": _text_array()})
    item = _schema(properties, [*fields, "new_risks", "supporting_claim_ids"])
    return _schema({"mechanisms": {"type": "array", "items": item}}, ["mechanisms"])


def _candidate_schema() -> dict[str, Any]:
    string_fields = [
        "family",
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
    ]
    properties: dict[str, Any] = {field: {"type": "string"} for field in string_fields}
    properties.update(
        {
            "assumption_indexes": {"type": "array", "items": {"type": "integer"}},
            "transformations_used": _text_array(),
            "mechanism_indexes": {"type": "array", "items": {"type": "integer"}},
            "value_creation_chain": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    key: {"type": "string"}
                    for key in (
                        "current_constraint",
                        "intervention",
                        "workflow_or_incentive_change",
                        "operational_or_economic_effect",
                        "buyer_value",
                        "value_capture",
                    )
                },
                "required": [
                    "current_constraint",
                    "intervention",
                    "workflow_or_incentive_change",
                    "operational_or_economic_effect",
                    "buyer_value",
                    "value_capture",
                ],
            },
            "critical_dependencies": _text_array(),
            "new_risks": _text_array(),
            "evidence_claim_ids": _text_array(),
            "unknowns": _text_array(),
            "validation_questions": _text_array(),
        }
    )
    required = [
        *string_fields,
        "assumption_indexes",
        "transformations_used",
        "mechanism_indexes",
        "value_creation_chain",
        "critical_dependencies",
        "new_risks",
        "evidence_claim_ids",
        "unknowns",
        "validation_questions",
    ]
    return _schema({"candidates": {"type": "array", "items": _schema(properties, required)}}, ["candidates"])


def _evidence_summary(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": record["claim_id"],
            "claim": record["claim"],
            "evidence_type": record["evidence_type"],
            "direction": record["supports_or_contradicts"],
            "confidence_tier": record["confidence_tier"],
        }
        for record in graph["records"]
    ]


def _emit(
    runtime: dict[str, Any],
    *,
    stage: str,
    status: str,
    code: str,
    now_provider: Callable[[], str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> None:
    append_stage_event(
        runtime,
        stage=stage,
        status=status,
        message_code=code,
        occurred_at=now_provider(),
    )
    if event_sink is not None:
        event_sink(deepcopy(runtime["stage_events"][-1]))


def _provider_failure_code(exc: Exception) -> str | None:
    for exc_type, code in _PROVIDER_FAILURES.items():
        if isinstance(exc, exc_type):
            return code
    return None


def _record_provider_metadata(
    runtime: dict[str, Any],
    provider: Any,
    *,
    role: str,
    operation: str,
    started_at: str,
    completed_at: str,
    explicit_result: dict[str, Any] | None = None,
) -> None:
    metadata: dict[str, Any] | None = None
    provider_name: str | None = None
    provider_run_id: str | None = None
    if explicit_result is not None:
        provider_name = explicit_result.get("provider")
        provider_run_id = explicit_result.get("provider_run_id")
        result_metadata = explicit_result.get("metadata")
        if isinstance(result_metadata, dict):
            metadata = result_metadata
    if metadata is None:
        candidate = getattr(provider, "last_run_metadata", None)
        if isinstance(candidate, dict):
            metadata = candidate
            provider_name = candidate.get("provider")
            provider_run_id = candidate.get("provider_response_id")
    if not isinstance(metadata, dict):
        return
    model = metadata.get("model")
    if not all(isinstance(item, str) and item.strip() for item in (provider_name, provider_run_id, model)):
        return
    record_provider_run(
        runtime,
        {
            "provider": provider_name,
            "provider_response_id": provider_run_id,
            "role": role,
            "model": model,
            "operation": operation,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": "completed",
            "usage": deepcopy(metadata.get("usage", {})) if isinstance(metadata.get("usage", {}), dict) else {},
            "source_count": metadata.get("source_count")
            if isinstance(metadata.get("source_count"), int) and not isinstance(metadata.get("source_count"), bool)
            else None,
        },
    )


def _incomplete(
    runtime: dict[str, Any],
    state: dict[str, Any],
    graph: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    stage: str,
    code: str,
    now_provider: Callable[[], str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    if runtime["status"] not in {"completed", "incomplete", "failed"}:
        _emit(
            runtime,
            stage=stage,
            status="blocked",
            code=f"{stage}_blocked",
            now_provider=now_provider,
            event_sink=event_sink,
        )
        mark_runtime_incomplete(runtime, code=code, stage=stage, occurred_at=now_provider())
    return {
        "runtime": runtime,
        "state": state,
        "evidence_graph": graph,
        "candidates": candidates,
        "decision_result": None,
        "report": None,
    }


def _failed(
    runtime: dict[str, Any],
    state: dict[str, Any],
    graph: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    stage: str,
    now_provider: Callable[[], str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    if runtime["status"] not in {"completed", "incomplete", "failed"}:
        _emit(
            runtime,
            stage=stage,
            status="failed",
            code=f"{stage}_failed",
            now_provider=now_provider,
            event_sink=event_sink,
        )
        mark_runtime_failed(
            runtime,
            code="internal_contract_violation",
            stage=stage,
            occurred_at=now_provider(),
        )
    return {
        "runtime": runtime,
        "state": state,
        "evidence_graph": graph,
        "candidates": candidates,
        "decision_result": None,
        "report": None,
    }


def _run_ideation(
    *,
    provider: Any,
    runtime: dict[str, Any],
    operation: str,
    objective: str,
    raw_idea: str,
    problem_context: dict[str, Any],
    assumption_context: list[dict[str, Any]],
    graph: dict[str, Any],
    schema: dict[str, Any],
    now_provider: Callable[[], str],
) -> dict[str, Any]:
    request = create_ideation_request(
        operation=operation,
        objective=objective,
        raw_idea=raw_idea,
        problem_context=problem_context,
        assumption_context=assumption_context,
        evidence_summary=_evidence_summary(graph),
        allowed_transformations=sorted(TRANSFORMATIONS),
        required_output_schema=schema,
        constraints=[
            "Do not create trusted IDs.",
            "Do not rank candidates or set official decisions.",
            "Use only Evidence Graph claim IDs supplied in evidence_summary.",
        ],
    )
    started = now_provider()
    result = run_ideation_operation(provider, request)
    completed = now_provider()
    _record_provider_metadata(
        runtime,
        provider,
        role="ideation",
        operation=operation,
        started_at=started,
        completed_at=completed,
    )
    return result


def _detailed_evidence_audit(graph: dict[str, Any]) -> dict[str, bool]:
    audit = audit_evidence_coverage(graph)
    records = graph["records"]
    support_ab = any(
        record["supports_or_contradicts"] == "supports"
        and record["confidence_tier"] in {"A", "B"}
        for record in records
    )
    return {
        "decision_ready": bool(audit["decision_ready"]),
        "counter_evidence_complete": audit["contradiction_count"] > 0,
        "freshness_ready": audit["stale_count"] == 0,
        "tier_ab_support_ready": support_ab,
        "noncritical_secondary_only": not any(
            record["confidence_tier"] in {"A", "B"} for record in records
        ),
    }


def _list_strings(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return list(value)


def _assemble_report(
    *,
    state: dict[str, Any],
    graph: dict[str, Any],
    analysis: dict[str, Any],
    baseline: dict[str, Any],
    assumptions: list[dict[str, Any]],
    challenges: list[dict[str, Any]],
    transformations: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    critiques: list[dict[str, Any]],
    decision_result: dict[str, Any],
) -> None:
    critique_by_id = {critique["target_id"]: critique for critique in critiques}
    selected_id = decision_result["selected_concept_id"] or baseline["baseline_id"]
    selected_critique = critique_by_id[selected_id]
    selected_candidate = next(
        (candidate for candidate in candidates if candidate["candidate_id"] == selected_id), None
    )
    records = graph["records"]
    supports = [record for record in records if record["supports_or_contradicts"] == "supports"]
    contradictions = [
        record for record in records if record["supports_or_contradicts"] == "contradicts"
    ]
    all_refs = [record["claim_id"] for record in records]

    if state["evidence_refs"]:
        raise ValueError("report assembly expects evidence refs to be attached exactly once")
    attach_evidence_refs(state, graph, all_refs)

    critical_unknowns = list(dict.fromkeys(baseline["unknowns"]))
    for candidate in candidates:
        for unknown in candidate["unknowns"]:
            if unknown not in critical_unknowns:
                critical_unknowns.append(unknown)
    if not critical_unknowns:
        critical_unknowns = ["No material unknown was recorded; validate buyer behavior before capital commitment."]

    primary_value = (
        selected_candidate["value_creation_chain"]["buyer_value"]
        if selected_candidate is not None
        else baseline["value_capture_hypothesis"]
    )
    evolution_delta = (
        f"Adopt evolved concept: {selected_candidate['one_sentence_concept']}"
        if selected_candidate is not None
        else "Retain the original concept; no evolved candidate passed the material-improvement rule."
    )
    if decision_result["decision"] in {"HOLD", "KILL"}:
        evolution_delta = f"No development handoff: official decision is {decision_result['decision']}."

    reasons_for = [
        selected_critique["strongest_reason_for"],
        decision_result["decision_reasons"][0],
        f"Agent MD feasibility for the original workflow is {analysis['feasibility_level']}.",
    ]
    reasons_against = [
        selected_critique["strongest_reason_against"],
        baseline["risks"][0] if baseline["risks"] else "Operational risk remains to be validated.",
        "Counter-evidence remains registered in the Evidence Graph and is not discarded.",
    ]

    market_records = [record for record in records if record["market_size"] is not None]
    current_market = []
    forecast_market = []
    growth = []
    for record in market_records:
        market = record["market_size"]
        current_market.append(
            {
                "label": f"{market['base_year']}: {market['base_value']} {market['unit']} {market['currency']}",
                "evidence_refs": [record["claim_id"]],
            }
        )
        if market["forecast_year"] is not None:
            forecast_market.append(
                {
                    "label": f"{market['forecast_year']}: {market['forecast_value']} {market['unit']} {market['currency']}",
                    "evidence_refs": [record["claim_id"]],
                }
            )
        if market["cagr"] is not None:
            growth.append(
                {
                    "label": f"CAGR: {market['cagr']}",
                    "evidence_refs": [record["claim_id"]],
                }
            )

    market_status = next(
        (record["claim"] for record in records if record["evidence_type"] == "market_status"),
        "Market stage is not established by an admissible dedicated market-status source.",
    )
    why_now = supports[0]["claim"] if supports else "No positive external evidence was admitted."
    next_validation = (
        decision_result["next_validation"]
        or selected_critique["cheapest_next_validation"]
    )

    state["executive_brief"] = {
        "thesis": f"{decision_result['decision']}: {decision_result['decision_reasons'][0]}",
        "why_now": why_now,
        "evolution_delta": evolution_delta,
        "market_snapshot": {
            "stage": market_status,
            "current_market": current_market,
            "forecast_market": forecast_market,
            "growth": growth,
            "buyer": selected_candidate["primary_buyer"] if selected_candidate else baseline["primary_buyer"],
        },
        "best_customer": selected_candidate["primary_buyer"] if selected_candidate else baseline["primary_buyer"],
        "business_value": primary_value,
        "reasons_for": reasons_for,
        "reasons_against": reasons_against,
        "critical_unknowns": critical_unknowns,
        "cheapest_next_validation": {
            "action": next_validation,
            "pass_condition": "The validation resolves the decision-critical uncertainty with traceable evidence.",
            "fail_condition": "The validation contradicts the value thesis or leaves the material uncertainty unresolved.",
        },
        "evidence_refs": all_refs,
    }

    def summary(items: list[str], fallback: str) -> str:
        cleaned = [item for item in items if isinstance(item, str) and item.strip()]
        return " ".join(cleaned) if cleaned else fallback

    details_text = {
        "original_idea_intent": state["raw_idea"],
        "underlying_problem": analysis["problem"],
        "market_definition": records[0]["population_or_market_definition"] if records else "No admissible market definition.",
        "global_market_status": market_status,
        "market_size_forecast": (
            summary([entry["label"] for entry in current_market + forecast_market + growth], "No admissible market-size estimate was established.")
        ),
        "competitive_landscape": summary(
            [record["claim"] for record in records if record["evidence_type"] in {"competitors", "prior_art"}],
            "No admissible competitive-landscape claim was established.",
        ),
        "customer_economics": baseline["value_capture_hypothesis"],
        "assumption_map": summary([item["statement"] for item in assumptions], "No assumptions were admitted."),
        "assumption_destruction": summary([item["challenge_question"] for item in challenges], "No assumption challenges were admitted."),
        "cross_industry_transfer": summary([item["mechanism_name"] + ": " + item["transfer_logic"] for item in mechanisms], "No mechanism transfer was admitted."),
        "candidate_forge": summary([item["name"] + ": " + item["one_sentence_concept"] for item in candidates], "No candidates were admitted."),
        "candidate_critique": summary(
            [critique["strongest_reason_for"] + " / " + critique["strongest_reason_against"] for critique in critiques],
            "No independent critiques were admitted.",
        ),
        "evolution_delta": evolution_delta,
        "evidence_for": summary([record["claim"] for record in supports], "No supporting evidence was admitted."),
        "evidence_against": summary([record["claim"] for record in contradictions], "No contradicting evidence was admitted."),
        "agent_md_gate": f"Automation {analysis['automation_level']}; feasibility {analysis['feasibility_level']}.",
        "risk_register": summary(baseline["risks"] + [risk for candidate in candidates for risk in candidate["new_risks"]], "No risks recorded."),
        "what_must_be_true": summary(baseline["critical_dependencies"] + critical_unknowns, "No dependencies recorded."),
        "validation_plan": next_validation,
        "final_decision": f"{decision_result['decision']} with {decision_result['confidence']} confidence: {'; '.join(decision_result['decision_reasons'])}",
    }
    if set(details_text) != DETAIL_SECTION_KEYS:
        raise ValueError("report assembly section set does not match canonical contract")
    state["detailed_analysis"] = {
        section: {"summary": details_text[section], "evidence_refs": all_refs}
        for section in DETAIL_SECTION_KEYS
    }
    state["report_status"] = "complete"
    validate_state_evidence_against_graph(state, graph)
    validate_complete_report(state)


def run_evolution(
    idea: str,
    *,
    research_provider: Any,
    ideation_provider: Any,
    evaluation_provider: Any,
    now_provider: Callable[[], str],
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one complete evolution assessment or return a truthful terminal failure state."""
    analysis = analyze_idea(idea)
    started_at = now_provider()
    evolution_id = _digest("evo", {"idea": idea})
    runtime_id = _digest("run", {"evolution_id": evolution_id, "started_at": started_at})
    state = create_evolution_state(idea, evolution_id)
    state["normalized_intent"] = analysis["problem"]
    validate_evolution_state(state)
    graph = create_evidence_graph(evolution_id)
    runtime = create_runtime_record(runtime_id, evolution_id, started_at)
    candidates: list[dict[str, Any]] = []

    def begin(stage: str) -> None:
        _emit(runtime, stage=stage, status="started", code=f"{stage}_started", now_provider=now_provider, event_sink=event_sink)

    def complete(stage: str) -> None:
        _emit(runtime, stage=stage, status="completed", code=f"{stage}_completed", now_provider=now_provider, event_sink=event_sink)

    begin("capture")
    complete("capture")

    # Landscape research.
    stage = "landscape_research"
    begin(stage)
    landscape_request = create_research_request(
        research_id=_digest("research", {"evolution_id": evolution_id, "pass": "landscape"}),
        evolution_id=evolution_id,
        pass_type="landscape",
        question="What market, buyer, workflow, and counter-evidence bears on this idea?",
        queries=[f"{idea} market buyer workflow evidence", f"{idea} failure limitations counter evidence"],
        required_evidence_categories=["market_status", "counter_evidence"],
        candidate_ids=[],
    )
    try:
        provider_started = now_provider()
        landscape_result = research_provider.research(deepcopy(landscape_request))
        provider_completed = now_provider()
        _record_provider_metadata(
            runtime,
            research_provider,
            role="research",
            operation="landscape",
            started_at=provider_started,
            completed_at=provider_completed,
            explicit_result=landscape_result,
        )
        ingest_provider_result(landscape_request, graph, landscape_result)
        complete_research_pass(landscape_request, graph)
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="research_insufficient", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    landscape_claims = [record["claim_id"] for record in graph["records"]]
    baseline = create_baseline(
        graph=graph,
        evolution_id=evolution_id,
        raw_idea=idea,
        problem_framing=analysis["problem"],
        primary_buyer=analysis["customer"],
        user=analysis["customer"],
        workflow=idea,
        value_capture_hypothesis="Create measurable value by reducing repeated manual work and decision delay.",
        automation_thesis=f"Agent MD automation assessment: {analysis['automation_level']}",
        critical_dependencies=["Validated workflow data access", "Buyer confirmation of measurable operational value"],
        risks=list(analysis["risks"]),
        evidence_claim_ids=landscape_claims,
        unknowns=["Buyer willingness to pay and workflow adoption remain to be validated."],
        validation_questions=["Will the target buyer pay to remove this recurring workflow cost?"],
    )

    # Assumptions + challenges.
    stage = "assumption_analysis"
    begin(stage)
    try:
        assumption_output = _run_ideation(
            provider=ideation_provider,
            runtime=runtime,
            operation="extract_assumptions",
            objective="Extract evidence-aware assumptions in the raw idea without creating trusted IDs.",
            raw_idea=idea,
            problem_context={"analysis": analysis, "baseline": baseline},
            assumption_context=[],
            graph=graph,
            schema=_assumption_schema(),
            now_provider=now_provider,
        )
        drafts = assumption_output.get("assumptions")
        if not isinstance(drafts, list) or not drafts:
            raise ValueError("assumptions output must be a non-empty list")
        assumptions = [
            create_assumption(graph=graph, evolution_id=evolution_id, **draft)
            for draft in drafts
        ]

        challenge_output = _run_ideation(
            provider=ideation_provider,
            runtime=runtime,
            operation="challenge_assumptions",
            objective="Challenge each material assumption by removal or inversion.",
            raw_idea=idea,
            problem_context={"analysis": analysis, "baseline": baseline},
            assumption_context=assumptions,
            graph=graph,
            schema=_challenge_schema(),
            now_provider=now_provider,
        )
        challenge_drafts = challenge_output.get("challenges")
        if not isinstance(challenge_drafts, list) or not challenge_drafts:
            raise ValueError("challenges output must be a non-empty list")
        challenges = []
        for draft in challenge_drafts:
            if not isinstance(draft, dict):
                raise ValueError("challenge draft must be an object")
            item = deepcopy(draft)
            index = item.pop("assumption_index", None)
            if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(assumptions):
                raise ValueError("challenge assumption_index is invalid")
            challenges.append(create_assumption_challenge(assumption_id=assumptions[index]["assumption_id"], **item))
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="provider_schema_mismatch", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Reframing.
    stage = "reframing"
    begin(stage)
    try:
        reframe_output = _run_ideation(
            provider=ideation_provider,
            runtime=runtime,
            operation="propose_reframes",
            objective="Apply material perspective transformations to the challenged assumptions.",
            raw_idea=idea,
            problem_context={"analysis": analysis, "challenges": challenges},
            assumption_context=assumptions,
            graph=graph,
            schema=_transformation_schema(),
            now_provider=now_provider,
        )
        transformation_drafts = reframe_output.get("transformations")
        if not isinstance(transformation_drafts, list) or not transformation_drafts:
            raise ValueError("transformations output must be a non-empty list")
        transformations = [create_transformation_test(**draft) for draft in transformation_drafts]
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="provider_schema_mismatch", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Mechanism transfer.
    stage = "mechanism_transfer"
    begin(stage)
    try:
        mechanism_output = _run_ideation(
            provider=ideation_provider,
            runtime=runtime,
            operation="discover_mechanisms",
            objective="Transfer causal mechanisms from other domains, not brand analogies.",
            raw_idea=idea,
            problem_context={"analysis": analysis, "transformations": transformations},
            assumption_context=assumptions,
            graph=graph,
            schema=_mechanism_schema(),
            now_provider=now_provider,
        )
        mechanism_drafts = mechanism_output.get("mechanisms")
        if not isinstance(mechanism_drafts, list) or not mechanism_drafts:
            raise ValueError("mechanisms output must be a non-empty list")
        mechanisms = [create_mechanism_transfer(graph=graph, **draft) for draft in mechanism_drafts]
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="provider_schema_mismatch", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Candidate forge.
    stage = "candidate_forge"
    begin(stage)
    try:
        candidate_output = _run_ideation(
            provider=ideation_provider,
            runtime=runtime,
            operation="forge_candidates",
            objective="Forge structurally distinct candidate concepts across the four canonical families.",
            raw_idea=idea,
            problem_context={"analysis": analysis, "transformations": transformations, "mechanisms": mechanisms},
            assumption_context=assumptions,
            graph=graph,
            schema=_candidate_schema(),
            now_provider=now_provider,
        )
        candidate_drafts = candidate_output.get("candidates")
        if not isinstance(candidate_drafts, list) or not candidate_drafts:
            raise ValueError("candidate output must be a non-empty list")
        for draft in candidate_drafts:
            if not isinstance(draft, dict):
                raise ValueError("candidate draft must be an object")
            item = deepcopy(draft)
            assumption_indexes = item.pop("assumption_indexes", None)
            mechanism_indexes = item.pop("mechanism_indexes", None)
            if not isinstance(assumption_indexes, list) or not isinstance(mechanism_indexes, list):
                raise ValueError("candidate draft indexes must be lists")
            if any(
                not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(assumptions)
                for index in assumption_indexes
            ):
                raise ValueError("candidate assumption index is invalid")
            if any(
                not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(mechanisms)
                for index in mechanism_indexes
            ):
                raise ValueError("candidate mechanism index is invalid")
            candidates.append(
                create_candidate(
                    graph=graph,
                    assumptions_broken=[assumptions[index]["assumption_id"] for index in assumption_indexes],
                    mechanism_transfer_ids=[mechanisms[index]["transfer_id"] for index in mechanism_indexes],
                    **item,
                )
            )
        candidate_audit = audit_candidate_set(
            graph,
            candidates,
            transformations,
            mechanisms,
        )
        if not candidate_audit["forge_ready"]:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="candidate_admission_blocked", now_provider=now_provider, event_sink=event_sink)
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="candidate_admission_blocked", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Collision research.
    stage = "collision_research"
    begin(stage)
    collision_request = create_research_request(
        research_id=_digest("research", {"evolution_id": evolution_id, "pass": "collision"}),
        evolution_id=evolution_id,
        pass_type="collision",
        question="What prior art, competitors, failures, and blockers collide with these evolved candidates?",
        queries=[
            "prior art and competing products for evolved workflow concepts",
            "failed precedents regulation technical blockers for evolved workflow concepts",
        ],
        required_evidence_categories=["prior_art", "competitors", "failure_or_blockers"],
        candidate_ids=[candidate["candidate_id"] for candidate in candidates],
    )
    try:
        provider_started = now_provider()
        collision_result = research_provider.research(deepcopy(collision_request))
        provider_completed = now_provider()
        _record_provider_metadata(
            runtime,
            research_provider,
            role="research",
            operation="collision",
            started_at=provider_started,
            completed_at=provider_completed,
            explicit_result=collision_result,
        )
        ingest_provider_result(collision_request, graph, collision_result)
        complete_research_pass(collision_request, graph)
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="collision_research_incomplete", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Independent evaluation.
    stage = "independent_evaluation"
    begin(stage)
    feasibility_level = analysis["feasibility_level"]
    feasibility_artifacts = {
        baseline["baseline_id"]: {
            "level": feasibility_level,
            "blocking_dependency_resolved": feasibility_level not in {"T1", "T2"},
            "resolution_path_exists": feasibility_level != "T1",
        },
        **{
            candidate["candidate_id"]: {
                "level": feasibility_level,
                "blocking_dependency_resolved": feasibility_level not in {"T1", "T2"},
                "resolution_path_exists": feasibility_level != "T1",
            }
            for candidate in candidates
        },
    }
    collision_state = {"status": "complete", "unresolved_requests": []}
    evaluation_request = build_evaluation_request(
        baseline=baseline,
        candidates=candidates,
        graph=graph,
        candidate_admission_audit=candidate_audit,
        feasibility_artifacts=feasibility_artifacts,
        collision_state=collision_state,
    )
    try:
        provider_started = now_provider()
        raw_evaluation = evaluation_provider.evaluate(deepcopy(evaluation_request))
        provider_completed = now_provider()
        _record_provider_metadata(
            runtime,
            evaluation_provider,
            role="evaluation",
            operation="independent_evaluation",
            started_at=provider_started,
            completed_at=provider_completed,
        )
        ingested = ingest_evaluator_output(
            raw_evaluation,
            graph=graph,
            baseline=baseline,
            candidates=candidates,
        )
        critiques = ingested["critiques"]
    except Exception as exc:
        failure = _provider_failure_code(exc)
        if failure:
            return _incomplete(runtime, state, graph, candidates, stage=stage, code=failure, now_provider=now_provider, event_sink=event_sink)
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return _incomplete(runtime, state, graph, candidates, stage=stage, code="evaluator_unavailable", now_provider=now_provider, event_sink=event_sink)
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Deterministic decision.
    stage = "decision"
    begin(stage)
    try:
        critique_by_id = {critique["target_id"]: critique for critique in critiques}
        if set(critique_by_id) != {baseline["baseline_id"], *[candidate["candidate_id"] for candidate in candidates]}:
            raise ValueError("independent evaluator must critique baseline and every candidate")
        evidence_audit = _detailed_evidence_audit(graph)
        baseline_critique = critique_by_id[baseline["baseline_id"]]
        baseline_classification = classify_option(
            baseline_critique,
            unresolved_collision_requests=[],
            feasibility_artifact=feasibility_artifacts[baseline["baseline_id"]],
            evidence_audit=evidence_audit,
        )
        baseline_confidence = derive_confidence(
            baseline_critique,
            classification=baseline_classification["classification"],
            unresolved_collision_requests=[],
            evidence_audit=evidence_audit,
        )
        candidate_critiques = [critique_by_id[candidate["candidate_id"]] for candidate in candidates]
        candidate_classifications = {}
        candidate_confidences = {}
        for candidate, critique in zip(candidates, candidate_critiques):
            candidate_id = candidate["candidate_id"]
            classification = classify_option(
                critique,
                unresolved_collision_requests=[],
                feasibility_artifact=feasibility_artifacts[candidate_id],
                evidence_audit=evidence_audit,
            )
            candidate_classifications[candidate_id] = classification
            candidate_confidences[candidate_id] = derive_confidence(
                critique,
                classification=classification["classification"],
                unresolved_collision_requests=[],
                evidence_audit=evidence_audit,
            )
        decision_result = decide_evolution(
            baseline_critique=baseline_critique,
            candidate_critiques=candidate_critiques,
            baseline_classification=baseline_classification,
            candidate_classifications=candidate_classifications,
            baseline_confidence=baseline_confidence,
            candidate_confidences=candidate_confidences,
            comparison_validation_action="Run the cheapest decision-critical buyer/workflow validation before development handoff.",
        )
        state = apply_decision_to_state(state, decision_result, candidates)
    except Exception:
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)

    # Report assembly.
    stage = "report_assembly"
    begin(stage)
    try:
        _assemble_report(
            state=state,
            graph=graph,
            analysis=analysis,
            baseline=baseline,
            assumptions=assumptions,
            challenges=challenges,
            transformations=transformations,
            mechanisms=mechanisms,
            candidates=candidates,
            critiques=critiques,
            decision_result=decision_result,
        )
    except Exception:
        return _failed(runtime, state, graph, candidates, stage=stage, now_provider=now_provider, event_sink=event_sink)
    complete(stage)
    mark_runtime_completed(runtime, occurred_at=now_provider())

    return {
        "runtime": runtime,
        "state": state,
        "evidence_graph": graph,
        "candidates": candidates,
        "decision_result": decision_result,
        "report": state["executive_brief"],
    }
