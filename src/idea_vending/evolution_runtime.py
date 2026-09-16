"""E2A integration layer over the stable E1 evolution runtime.

The core runtime remains byte-identical to the verified E1 implementation. This
module captures the already-produced independent evaluator output and derives
per-candidate Reality Assessments deterministically without a second provider
call or any provider-controlled verdict.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.idea_vending import evolution_runtime_core as _core
from src.idea_vending import evolution_schema_core as _schema_core
from src.idea_vending.evolution_schema import validate_complete_report as _validate_e2a_complete_report
from src.idea_vending.independent_evaluator import ingest_evaluator_output
from src.idea_vending.reality_evaluation import derive_reality_assessment

# Preserve the E1 module surface, including private helpers used by tests or
# integration code, while overriding only run_evolution below.
for _name in dir(_core):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_core, _name)


def _validate_core_report_phase(state: dict[str, Any]) -> None:
    """Allow the stable E1 assembler to validate before E2A assessments are attached."""
    legacy = deepcopy(state)
    legacy.pop("candidate_reality_assessments", None)
    _schema_core.validate_complete_report(legacy)


# E1 assembles the report before E2A can derive Reality Assessments. Keep that
# internal phase on the legacy validator; the public E2A validator runs after
# the assessments are attached below.
_core.validate_complete_report = _validate_core_report_phase


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


def _derive_candidate_reality_assessments(
    *,
    result: dict[str, Any],
    captured_request: dict[str, Any],
    raw_evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
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
    critique_by_id = {
        critique["target_id"]: critique
        for critique in ingested["critiques"]
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
    return assessments


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
    capturing_evaluator = _CapturingEvaluationProvider(evaluation_provider)
    result = _core.run_evolution(
        idea,
        research_provider=research_provider,
        ideation_provider=ideation_provider,
        evaluation_provider=capturing_evaluator,
        now_provider=now_provider,
        event_sink=event_sink,
    )

    if result.get("runtime", {}).get("status") != "completed":
        return result
    if capturing_evaluator.request is None or capturing_evaluator.raw_output is None:
        raise ValueError("completed runtime is missing captured independent evaluation")

    assessments = _derive_candidate_reality_assessments(
        result=result,
        captured_request=capturing_evaluator.request,
        raw_evaluation=capturing_evaluator.raw_output,
    )
    result["candidate_reality_assessments"] = assessments
    result["state"]["candidate_reality_assessments"] = deepcopy(assessments)
    _validate_e2a_complete_report(result["state"])
    return result
