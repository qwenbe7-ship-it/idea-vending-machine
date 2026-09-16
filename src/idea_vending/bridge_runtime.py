"""Trusted orchestration for importing the Forge half of ChatGPT Plus Bridge Mode."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from src.idea_vending.bridge_contract import BRIDGE_VERSION, validate_bridge_envelope, validate_bridge_json
from src.idea_vending.bridge_replay import BridgeIdeationReplay, BridgeResearchReplay
from src.idea_vending.evolution_runtime import ForgeArtifact, run_forge_phase

_FORGE_RESULT_KEYS = {
    "landscape_research",
    "extract_assumptions",
    "challenge_assumptions",
    "propose_reframes",
    "discover_mechanisms",
    "forge_candidates",
    "collision_research",
}


def bridge_payload_digest(envelope: dict[str, Any]) -> str:
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

    retrieved_date = _retrieved_date_from_now(now_provider)
    research = BridgeResearchReplay(
        result,
        session_id=session_id,
        retrieved_date_provider=lambda: retrieved_date,
    )
    ideation = BridgeIdeationReplay(result, research)
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
    return forge
