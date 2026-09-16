"""Traceability bridge between v0.3 Evolution State and Evidence Graph."""

from __future__ import annotations

from typing import Any

from src.idea_vending.evidence_graph import validate_evidence_record
from src.idea_vending.evolution_schema import (
    validate_complete_report,
    validate_evolution_state,
)


def _claim_ids_from_graph(graph: dict[str, Any]) -> set[str]:
    if not isinstance(graph, dict) or set(graph) != {"evolution_id", "records"}:
        raise ValueError("graph does not match the Evidence Graph contract")
    if not isinstance(graph["records"], list):
        raise ValueError("Evidence Graph records must be a list")

    claim_ids: set[str] = set()
    for record in graph["records"]:
        validate_evidence_record(record)
        claim_id = record["claim_id"]
        if claim_id in claim_ids:
            raise ValueError("Evidence Graph contains duplicate claim_id")
        claim_ids.add(claim_id)
    return claim_ids


def validate_state_evidence_against_graph(
    state: dict[str, Any], graph: dict[str, Any]
) -> None:
    """Require every state-level claim reference to exist in the matching graph."""
    validate_evolution_state(state)
    if graph.get("evolution_id") != state["evolution_id"]:
        raise ValueError("state and Evidence Graph evolution_id must match")

    graph_claim_ids = _claim_ids_from_graph(graph)
    refs = state["evidence_refs"]
    if len(refs) != len(set(refs)):
        raise ValueError("state evidence_refs must not contain duplicate references")

    missing = sorted(set(refs) - graph_claim_ids)
    if missing:
        raise ValueError(
            "state references claim IDs absent from Evidence Graph: " + ", ".join(missing)
        )

    if state["report_status"] == "complete":
        validate_complete_report(state)


def attach_evidence_refs(
    state: dict[str, Any], graph: dict[str, Any], claim_ids: list[str]
) -> None:
    """Attach known graph claim IDs without altering any other evolution-state field."""
    validate_evolution_state(state)
    if not isinstance(claim_ids, list) or not claim_ids:
        raise ValueError("claim_ids must be a non-empty list")
    if not all(isinstance(claim_id, str) and claim_id.strip() for claim_id in claim_ids):
        raise ValueError("claim_ids must contain only non-empty strings")
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("claim_ids must not contain duplicate values")
    if graph.get("evolution_id") != state["evolution_id"]:
        raise ValueError("state and Evidence Graph evolution_id must match")

    graph_claim_ids = _claim_ids_from_graph(graph)
    unknown = sorted(set(claim_ids) - graph_claim_ids)
    if unknown:
        raise ValueError("unknown claim_id: " + ", ".join(unknown))

    existing = set(state["evidence_refs"])
    already_registered = sorted(existing.intersection(claim_ids))
    if already_registered:
        raise ValueError(
            "claim_id already registered in state: " + ", ".join(already_registered)
        )

    state["evidence_refs"].extend(claim_ids)
    validate_state_evidence_against_graph(state, graph)
