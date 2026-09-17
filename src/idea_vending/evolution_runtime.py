"""E2A integration layer over the stable E1 evolution runtime.

The core runtime remains byte-identical to the verified E1 implementation. This
module captures the already-produced independent evaluator output and derives
per-candidate Reality Assessments deterministically without a second provider
call or any provider-controlled verdict. Intent-aware providers are additionally
wrapped here so intent interpretation and bounded research planning happen before
landscape research without rewriting the stable deterministic core.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.idea_vending import evidence_attachment as _evidence_attachment
from src.idea_vending import evolution_runtime_core as _core
from src.idea_vending import evolution_schema_core as _schema_core
from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evolution_schema import validate_complete_report as _validate_e2a_complete_report
from src.idea_vending.ideation_contract import run_ideation_operation
from src.idea_vending.independent_evaluator import ingest_evaluator_output
from src.idea_vending.intent_model import validate_intent_model
from src.idea_vending.intent_planner import (
    build_intent_request,
    build_research_plan_request,
    flatten_research_questions,
    validate_research_plan,
)
from src.idea_vending.provider_transport import ProviderTimeout
from src.idea_vending.reality_evaluation import derive_reality_assessment

# Preserve the E1 module surface, including private helpers used by tests or
# integration code, while overriding only run_evolution below.
for _name in dir(_core):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_core, _name)


_CORE_IDEATION_OPERATIONS = {
    "extract_assumptions",
    "challenge_assumptions",
    "propose_reframes",
    "discover_mechanisms",
    "forge_candidates",
}
_COLLISION_PLAN_CATEGORIES = (
    "alternatives_incumbents",
    "implementation_feasibility",
    "regulation_security",
    "failure_blockers",
)


def _legacy_state(state: dict[str, Any]) -> dict[str, Any]:
    legacy = deepcopy(state)
    legacy.pop("candidate_reality_assessments", None)
    return legacy


def _validate_core_report_phase(state: dict[str, Any]) -> None:
    """Allow the stable E1 assembler to validate before E2A assessments are attached."""
    _schema_core.validate_complete_report(_legacy_state(state))


def _validate_core_state_evidence_phase(
    state: dict[str, Any], graph: dict[str, Any]
) -> None:
    """Preserve graph traceability during E1 assembly without requiring E2A output early."""
    legacy = _legacy_state(state)
    _schema_core.validate_evolution_state(legacy)
    if graph.get("evolution_id") != legacy["evolution_id"]:
        raise ValueError("state and Evidence Graph evolution_id must match")

    graph_claim_ids = _evidence_attachment._claim_ids_from_graph(graph)
    refs = legacy["evidence_refs"]
    if len(refs) != len(set(refs)):
        raise ValueError("state evidence_refs must not contain duplicate references")
    missing = sorted(set(refs) - graph_claim_ids)
    if missing:
        raise ValueError(
            "state references claim IDs absent from Evidence Graph: " + ", ".join(missing)
        )
    if legacy["report_status"] == "complete":
        _schema_core.validate_complete_report(legacy)


# E1 assembles the report before E2A can derive Reality Assessments. Keep only
# that internal phase on the legacy validators; public E2A validators remain
# strict and run after the assessments are attached below.
_core.validate_complete_report = _validate_core_report_phase
_core.validate_state_evidence_against_graph = _validate_core_state_evidence_phase


def _supports_intent_planning(provider: Any) -> bool:
    """Return whether an ideation provider can execute the two new operations.

    Providers may opt in explicitly. The currently shipped OpenAI adapter already
    accepts the generic structured ideation envelope, so it is recognized here
    while older injected test/legacy providers keep their verified behavior.
    """
    explicit = getattr(provider, "supports_intent_planning", None)
    if explicit is not None:
        return explicit is True
    provider_type = type(provider)
    return (
        provider_type.__module__ == "src.idea_vending.openai_provider"
        and provider_type.__name__ == "OpenAIResponsesProvider"
    )


def _prepare_intent_context(idea: str, ideation_provider: Any) -> dict[str, Any] | None:
    if not _supports_intent_planning(ideation_provider):
        return None
    raw_intent = run_ideation_operation(ideation_provider, build_intent_request(idea))
    intent = validate_intent_model(raw_intent)
    raw_plan = run_ideation_operation(
        ideation_provider,
        build_research_plan_request(intent),
    )
    plan = validate_research_plan(raw_plan)
    return {
        "intent_model": intent,
        "research_plan": plan,
    }


def _intent_research_summary(intent: dict[str, Any]) -> str:
    def joined(values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "unknown"
        return " | ".join(str(value) for value in values)

    return " ".join(
        [
            f"Intent objective: {intent['primary_objective']}",
            f"Desired outcome: {intent['desired_outcome']}",
            f"Hard constraints: {joined(intent['hard_constraints'])}",
            f"Success metrics: {joined(intent['success_metrics'])}",
            f"Material unknowns: {joined(intent['material_unknowns'])}",
        ]
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip() and value not in result:
            result.append(value)
    return result


class _IntentAwareResearchProvider:
    """Enrich stable research requests with validated intent and plan questions."""

    def __init__(self, delegate: Any, intent_context: dict[str, Any]) -> None:
        self._delegate = delegate
        self._context = deepcopy(intent_context)

    @property
    def last_run_metadata(self) -> Any:
        return getattr(self._delegate, "last_run_metadata", None)

    def research(self, request: dict[str, Any]) -> dict[str, Any]:
        forwarded = deepcopy(request)
        intent = self._context["intent_model"]
        plan = self._context["research_plan"]
        summary = _intent_research_summary(intent)
        if forwarded.get("pass_type") == "collision":
            planned = flatten_research_questions(
                plan,
                categories=_COLLISION_PLAN_CATEGORIES,
            )
        else:
            planned = flatten_research_questions(plan)
        forwarded["question"] = f"{forwarded['question']} {summary}"
        forwarded["queries"] = _dedupe_strings([*planned, *forwarded["queries"]])
        return self._delegate.research(forwarded)


class _E2AIdeationProvider:
    """Strengthen candidate Forge requests and attach validated intent context."""

    def __init__(
        self,
        delegate: Any,
        intent_context: dict[str, Any] | None = None,
    ) -> None:
        self._delegate = delegate
        self._intent_context = deepcopy(intent_context)

    @property
    def last_run_metadata(self) -> Any:
        return getattr(self._delegate, "last_run_metadata", None)

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        forwarded = deepcopy(request)
        if (
            self._intent_context is not None
            and forwarded.get("operation") in _CORE_IDEATION_OPERATIONS
        ):
            problem_context = deepcopy(forwarded.get("problem_context", {}))
            problem_context["intent_model"] = deepcopy(
                self._intent_context["intent_model"]
            )
            problem_context["research_plan"] = deepcopy(
                self._intent_context["research_plan"]
            )
            forwarded["problem_context"] = problem_context

        if forwarded.get("operation") == "forge_candidates":
            families = sorted(CANDIDATE_FAMILIES)
            forwarded["objective"] = (
                "Forge exactly ten structurally distinct candidate concepts, exactly one "
                "for each canonical E2A family."
            )
            constraints = list(forwarded.get("constraints", []))
            constraints.extend(
                [
                    "Return exactly ten candidates; do not omit, merge, or duplicate a family.",
                    "Canonical families are: " + ", ".join(families) + ".",
                ]
            )
            forwarded["constraints"] = constraints

            schema = deepcopy(forwarded.get("required_output_schema"))
            try:
                family_schema = schema["properties"]["candidates"]["items"]["properties"]["family"]
            except (KeyError, TypeError):
                raise ValueError("forge candidate schema does not expose family")
            if not isinstance(family_schema, dict):
                raise ValueError("forge candidate family schema must be an object")
            family_schema["enum"] = families
            forwarded["required_output_schema"] = schema
        return self._delegate.generate(forwarded)


class _CapturingEvaluationProvider:
    """Capture one evaluator request/result while transparently forwarding metadata."""

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.request: dict[str, Any] | None = None
        self.raw_output: dict[str, Any] | None = None

    @property
    def last_run_metadata(self) -> Any:
        return getattr(self._delegate, "last_run_metadata", None)

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.request = deepcopy(request)
        output = self._delegate.evaluate(request)
        self.raw_output = deepcopy(output)
        return output


class _ForgeBoundaryEvaluationProvider:
    """Capture the trusted evaluator request and stop before any Judge execution."""

    def __init__(self) -> None:
        self.request: dict[str, Any] | None = None

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        self.request = deepcopy(request)
        raise ProviderTimeout("forge phase boundary")


class ForgeArtifact(dict):
    """Trusted in-memory Forge artifact with non-serialized replay providers."""

    def __init__(self, *args: Any, research_provider: Any, ideation_provider: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._research_provider = research_provider
        self._ideation_provider = ideation_provider


def _derive_candidate_reality_assessments(
    *,
    result: dict[str, Any],
    captured_request: dict[str, Any],
    raw_evaluation: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = result.get("candidates")
    graph = result.get("evidence_graph")
    if not isinstance(candidates, list) or len(candidates) != 10:
        raise ValueError("completed E2A runtime must contain exactly ten candidates")
    if not isinstance(graph, dict):
        raise ValueError("completed E2A runtime must contain an Evidence Graph")

    baseline = captured_request.get("baseline")
    feasibility_artifacts = captured_request.get("feasibility_artifacts")
    collision_state = captured_request.get("collision_state")
    if not isinstance(baseline, dict):
        raise ValueError("captured evaluator request is missing baseline")
    if not isinstance(feasibility_artifacts, dict):
        raise ValueError("captured evaluator request is missing feasibility artifacts")
    if not isinstance(collision_state, dict):
        raise ValueError("captured evaluator request is missing collision state")

    unresolved = collision_state.get("unresolved_requests", [])
    if not isinstance(unresolved, list):
        raise ValueError("collision_state.unresolved_requests must be a list")

    ingested = ingest_evaluator_output(
        raw_evaluation,
        graph=graph,
        baseline=baseline,
        candidates=candidates,
    )
    critiques = ingested["critiques"]
    critique_by_id = {
        critique["target_id"]: critique
        for critique in critiques
        if critique.get("target_type") == "candidate"
    }
    if set(critique_by_id) != {candidate["candidate_id"] for candidate in candidates}:
        raise ValueError("every E2A candidate must have one independent critique")

    evidence_audit = _core._detailed_evidence_audit(graph)
    assessments: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        critique = critique_by_id[candidate_id]
        feasibility = feasibility_artifacts.get(candidate_id)
        if not isinstance(feasibility, dict):
            raise ValueError("candidate feasibility artifact is missing")
        gate_result = _core.classify_option(
            critique,
            unresolved_collision_requests=unresolved,
            feasibility_artifact=feasibility,
            evidence_audit=evidence_audit,
        )
        confidence = _core.derive_confidence(
            critique,
            classification=gate_result["classification"],
            unresolved_collision_requests=unresolved,
            evidence_audit=evidence_audit,
        )
        assessments.append(
            derive_reality_assessment(
                candidate=candidate,
                critique=critique,
                gate_result=gate_result,
                confidence=confidence,
            )
        )
    return assessments, critiques


def _intent_wrapped_providers(
    idea: str,
    *,
    research_provider: Any,
    ideation_provider: Any,
) -> tuple[dict[str, Any] | None, Any, Any]:
    intent_context = _prepare_intent_context(idea, ideation_provider)
    wrapped_research = (
        _IntentAwareResearchProvider(research_provider, intent_context)
        if intent_context is not None
        else research_provider
    )
    wrapped_ideation = _E2AIdeationProvider(ideation_provider, intent_context)
    return intent_context, wrapped_research, wrapped_ideation


def _apply_normalized_intent(
    result: dict[str, Any], intent_context: dict[str, Any] | None
) -> None:
    if intent_context is None:
        return
    state = result.get("state")
    if isinstance(state, dict):
        state["normalized_intent"] = intent_context["intent_model"]["primary_objective"]


def run_forge_phase(
    idea: str,
    *,
    research_provider: Any,
    ideation_provider: Any,
    now_provider: Any,
    event_sink: Any = None,
) -> ForgeArtifact:
    """Run the verified pipeline through collision research, then stop before Judge execution."""
    intent_context, wrapped_research, wrapped_ideation = _intent_wrapped_providers(
        idea,
        research_provider=research_provider,
        ideation_provider=ideation_provider,
    )
    boundary = _ForgeBoundaryEvaluationProvider()
    result = _core.run_evolution(
        idea,
        research_provider=wrapped_research,
        ideation_provider=wrapped_ideation,
        evaluation_provider=boundary,
        now_provider=now_provider,
        event_sink=event_sink,
    )
    _apply_normalized_intent(result, intent_context)
    if boundary.request is None:
        raise ValueError("forge phase did not reach the independent evaluation boundary")
    state = result.get("state")
    graph = result.get("evidence_graph")
    runtime = result.get("runtime")
    candidates = result.get("candidates")
    if not isinstance(state, dict) or not isinstance(graph, dict) or not isinstance(runtime, dict):
        raise ValueError("forge phase returned an invalid trusted intermediate result")
    if not isinstance(candidates, list) or len(candidates) != 10:
        raise ValueError("forge phase must contain exactly ten trusted candidates")
    request = boundary.request
    baseline = request.get("baseline")
    feasibility_artifacts = request.get("feasibility_artifacts")
    collision_state = request.get("collision_state")
    if not isinstance(baseline, dict) or not isinstance(feasibility_artifacts, dict) or not isinstance(collision_state, dict):
        raise ValueError("forge phase evaluator boundary is missing trusted context")
    artifact = {
        "analysis": analyze_idea(idea),
        "state": deepcopy(state),
        "evidence_graph": deepcopy(graph),
        "runtime": deepcopy(runtime),
        "baseline": deepcopy(baseline),
        "assumptions": [],
        "challenges": [],
        "transformations": [],
        "mechanisms": [],
        "candidates": deepcopy(candidates),
        "feasibility_artifacts": deepcopy(feasibility_artifacts),
        "collision_state": deepcopy(collision_state),
    }
    if intent_context is not None:
        artifact["intent_model"] = deepcopy(intent_context["intent_model"])
        artifact["research_plan"] = deepcopy(intent_context["research_plan"])
    return ForgeArtifact(
        artifact,
        research_provider=research_provider,
        ideation_provider=ideation_provider,
    )


def finalize_evolution_from_forge(
    forge_artifact: ForgeArtifact,
    *,
    evaluation_provider: Any,
    now_provider: Any,
    event_sink: Any = None,
) -> dict[str, Any]:
    """Replay a validated Forge input through the same public E2A runtime with a fresh Judge."""
    if not isinstance(forge_artifact, ForgeArtifact):
        raise ValueError("forge_artifact must be a trusted ForgeArtifact")
    state = forge_artifact.get("state")
    if not isinstance(state, dict) or not isinstance(state.get("raw_idea"), str):
        raise ValueError("forge_artifact is missing raw_idea")
    return run_evolution(
        state["raw_idea"],
        research_provider=forge_artifact._research_provider,
        ideation_provider=forge_artifact._ideation_provider,
        evaluation_provider=evaluation_provider,
        now_provider=now_provider,
        event_sink=event_sink,
    )


def _intent_provider_failure_result(
    idea: str,
    *,
    code: str,
    now_provider: Any,
    event_sink: Any = None,
) -> dict[str, Any]:
    """Preserve the stable runtime contract when pre-core intent capture cannot complete."""
    analysis = analyze_idea(idea)
    started_at = now_provider()
    evolution_id = _core._digest("evo", {"idea": idea})
    runtime_id = _core._digest(
        "run", {"evolution_id": evolution_id, "started_at": started_at}
    )
    state = _core.create_evolution_state(idea, evolution_id)
    state["normalized_intent"] = analysis["problem"]
    _core.validate_evolution_state(state)
    graph = _core.create_evidence_graph(evolution_id)
    runtime = _core.create_runtime_record(runtime_id, evolution_id, started_at)
    _core._emit(
        runtime,
        stage="capture",
        status="started",
        code="capture_started",
        now_provider=now_provider,
        event_sink=event_sink,
    )
    return _core._incomplete(
        runtime,
        state,
        graph,
        [],
        stage="capture",
        code=code,
        now_provider=now_provider,
        event_sink=event_sink,
    )


def run_evolution(
    idea: str,
    *,
    research_provider: Any,
    ideation_provider: Any,
    evaluation_provider: Any,
    now_provider: Any,
    event_sink: Any = None,
) -> dict[str, Any]:
    """Run E1 and attach ten deterministic E2A Reality Assessments on success."""
    try:
        intent_context, wrapped_research, e2a_ideation_provider = _intent_wrapped_providers(
            idea,
            research_provider=research_provider,
            ideation_provider=ideation_provider,
        )
    except Exception as exc:
        failure_code = _core._provider_failure_code(exc)
        if failure_code is None:
            raise
        return _intent_provider_failure_result(
            idea,
            code=failure_code,
            now_provider=now_provider,
            event_sink=event_sink,
        )
    capturing_evaluator = _CapturingEvaluationProvider(evaluation_provider)
    result = _core.run_evolution(
        idea,
        research_provider=wrapped_research,
        ideation_provider=e2a_ideation_provider,
        evaluation_provider=capturing_evaluator,
        now_provider=now_provider,
        event_sink=event_sink,
    )
    _apply_normalized_intent(result, intent_context)

    if result.get("runtime", {}).get("status") != "completed":
        return result
    if capturing_evaluator.request is None or capturing_evaluator.raw_output is None:
        raise ValueError("completed runtime is missing captured independent evaluation")

    assessments, critiques = _derive_candidate_reality_assessments(
        result=result,
        captured_request=capturing_evaluator.request,
        raw_evaluation=capturing_evaluator.raw_output,
    )
    result["candidate_reality_assessments"] = assessments
    result["critiques"] = deepcopy(critiques)
    result["state"]["candidate_reality_assessments"] = deepcopy(assessments)
    _validate_e2a_complete_report(result["state"])
    return result