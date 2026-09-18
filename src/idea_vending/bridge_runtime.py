"""Trusted orchestration for importing ChatGPT Plus Bridge Mode results."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from src.idea_vending.bridge_contract import BRIDGE_VERSION, validate_bridge_envelope, validate_bridge_json
from src.idea_vending.bridge_replay import (
    BridgeEvaluationReplay,
    BridgeIdeationReplay,
    BridgeResearchReplay,
)
from src.idea_vending.bridge_schema import validate_forge_bridge_result
from src.idea_vending.evolution_runtime import (
    ForgeArtifact,
    finalize_evolution_from_forge,
    run_forge_phase,
)
from src.idea_vending.intent_planner import build_conservative_intent_context

_FORGE_RESULT_KEYS = {
    "landscape_research",
    "extract_assumptions",
    "challenge_assumptions",
    "propose_reframes",
    "discover_mechanisms",
    "forge_candidates",
    "collision_research",
}
_JUDGE_RESULT_KEYS = {"critiques", "additional_evidence"}


def _execution_package_error(value: Any) -> str | None:
    """Recognize a Bridge execution package accidentally pasted into a result slot."""
    if not isinstance(value, dict):
        return None
    request_type = value.get("request_type")
    if request_type == "forge" and "result_contract" in value and "chatgpt_instruction" in value:
        return "bridge_forge_package_pasted_as_result"
    if request_type == "judge" and "result_contract" in value and "chatgpt_instruction" in value:
        return "bridge_judge_package_pasted_as_result"
    return None


def bridge_payload_digest(envelope: dict[str, Any]) -> str:
    if isinstance(envelope, dict):
        package_error = _execution_package_error(envelope.get("result"))
        if package_error is not None:
            raise ValueError(package_error)
    validate_bridge_json(envelope)
    encoded = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _retrieved_date_from_now(now_provider: Callable[[], str]) -> str:
    value = now_provider()
    if not isinstance(value, str) or len(value) < 10:
        raise ValueError("bridge_now_invalid")
    return value[:10]


def validate_and_run_forge_import(
    session_record: dict[str, Any],
    envelope: dict[str, Any],
    *,
    now_provider: Callable[[], str],
) -> ForgeArtifact:
    """Treat Forge output as untrusted provider material and replay it through all existing gates."""
    if isinstance(envelope, dict):
        package_error = _execution_package_error(envelope.get("result"))
        if package_error is not None:
            raise ValueError(package_error)
    validate_bridge_envelope(envelope)
    if not isinstance(session_record, dict):
        raise ValueError("bridge_session_invalid")
    session_id = session_record.get("bridge_session_id")
    raw_idea = session_record.get("raw_idea")
    state = session_record.get("state")
    if envelope["bridge_session_id"] != session_id:
        raise ValueError("bridge_session_mismatch")
    if envelope["bridge_version"] != BRIDGE_VERSION:
        raise ValueError("bridge_version_mismatch")
    if state != "forge_requested":
        raise ValueError("bridge_state_invalid")
    if not isinstance(raw_idea, str) or not raw_idea.strip():
        raise ValueError("bridge_session_idea_invalid")

    result = envelope["result"]
    if not isinstance(result, dict) or set(result) != _FORGE_RESULT_KEYS:
        raise ValueError("bridge_forge_result_invalid")
    validate_bridge_json(result)
    validate_forge_bridge_result(result)

    retrieved_date = _retrieved_date_from_now(now_provider)
    intent_context = build_conservative_intent_context(raw_idea)
    research = BridgeResearchReplay(
        result,
        session_id=session_id,
        retrieved_date_provider=lambda: retrieved_date,
    )
    ideation = BridgeIdeationReplay(
        result,
        research,
        intent_context=intent_context,
    )
    forge = run_forge_phase(
        raw_idea,
        research_provider=research,
        ideation_provider=ideation,
        now_provider=now_provider,
    )
    if forge["state"].get("decision") is not None:
        raise ValueError("bridge_forge_cannot_set_decision")
    if len(forge.get("candidates", [])) != 10:
        raise ValueError("bridge_forge_candidate_coverage_invalid")
    if forge.get("intent_model") != intent_context["intent_model"]:
        raise ValueError("bridge_intent_replay_mismatch")
    if forge.get("research_plan") != intent_context["research_plan"]:
        raise ValueError("bridge_research_plan_replay_mismatch")
    return forge


def _validate_judge_coverage(forge: ForgeArtifact, critiques: Any) -> None:
    if not isinstance(critiques, list) or len(critiques) != 11:
        raise ValueError("bridge_judge_critique_coverage_invalid")
    baseline = forge.get("baseline")
    candidates = forge.get("candidates")
    if not isinstance(baseline, dict) or not isinstance(candidates, list) or len(candidates) != 10:
        raise ValueError("trusted_forge_context_invalid")
    expected = {baseline["baseline_id"], *[candidate["candidate_id"] for candidate in candidates]}
    targets: list[str] = []
    for critique in critiques:
        if not isinstance(critique, dict):
            raise ValueError("bridge_judge_critique_invalid")
        target = critique.get("target_id")
        if not isinstance(target, str):
            raise ValueError("bridge_judge_target_invalid")
        targets.append(target)
    if len(targets) != len(set(targets)) or set(targets) != expected:
        raise ValueError("bridge_judge_critique_coverage_invalid")


def validate_and_finalize_judge_import(
    session_record: dict[str, Any],
    envelope: dict[str, Any],
    *,
    now_provider: Callable[[], str],
) -> dict[str, Any]:
    """Validate an independent Judge import and derive the official result server-side."""
    validate_bridge_envelope(envelope)
    if not isinstance(session_record, dict):
        raise ValueError("bridge_session_invalid")
    session_id = session_record.get("bridge_session_id")
    if envelope["bridge_session_id"] != session_id:
        raise ValueError("bridge_session_mismatch")
    if envelope["bridge_version"] != BRIDGE_VERSION:
        raise ValueError("bridge_version_mismatch")
    if session_record.get("state") != "judge_requested":
        raise ValueError("bridge_state_invalid")
    forge = session_record.get("trusted_forge")
    if not isinstance(forge, ForgeArtifact):
        raise ValueError("trusted_forge_invalid")

    result = envelope["result"]
    if not isinstance(result, dict) or set(result) != _JUDGE_RESULT_KEYS:
        raise ValueError("bridge_judge_result_invalid")
    validate_bridge_json(result)
    _validate_judge_coverage(forge, result["critiques"])
    additional_evidence = result["additional_evidence"]
    if not isinstance(additional_evidence, list):
        raise ValueError("bridge_additional_evidence_invalid")

    research = getattr(forge, "_research_provider", None)
    if not isinstance(research, BridgeResearchReplay):
        raise ValueError("trusted_forge_research_replay_invalid")
    research.set_additional_collision_evidence(additional_evidence)
    evaluator = BridgeEvaluationReplay(result, research)
    completed = finalize_evolution_from_forge(
        forge,
        evaluation_provider=evaluator,
        now_provider=now_provider,
    )
    runtime = completed.get("runtime")
    state = completed.get("state")
    if not isinstance(runtime, dict) or runtime.get("status") != "completed":
        raise ValueError("bridge_judge_finalization_incomplete")
    if not isinstance(state, dict) or state.get("decision") not in {"GO", "MODIFY", "HOLD", "KILL"}:
        raise ValueError("bridge_official_decision_missing")
    if len(completed.get("candidate_reality_assessments", [])) != 10:
        raise ValueError("bridge_reality_assessment_coverage_invalid")
    return completed