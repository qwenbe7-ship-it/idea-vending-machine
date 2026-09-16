"""Server-derived evidence summary for autonomous due-diligence runs."""

from __future__ import annotations

from typing import Any


_DECISIONS = {"GO", "MODIFY", "HOLD", "KILL"}


def derive_automation_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize only trusted runtime fields; never preserve provider-supplied summary data."""
    if not isinstance(result, dict):
        raise ValueError("autonomous result must be a dictionary")

    runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
    state = result.get("state") if isinstance(result.get("state"), dict) else {}
    graph = result.get("evidence_graph") if isinstance(result.get("evidence_graph"), dict) else {}

    records = graph.get("records") if isinstance(graph.get("records"), list) else []
    candidates = result.get("candidates") if isinstance(result.get("candidates"), list) else []
    critiques = result.get("critiques") if isinstance(result.get("critiques"), list) else []

    decision = state.get("decision")
    runtime_id = runtime.get("runtime_id")
    evidence_count = len(records)
    contradicting_count = sum(
        1
        for record in records
        if isinstance(record, dict) and record.get("supports_or_contradicts") == "contradicts"
    )

    return {
        "mode": "autonomous_due_diligence",
        "research_completed": runtime.get("status") == "completed" and evidence_count > 0,
        "evidence_count": evidence_count,
        "contradicting_evidence_count": contradicting_count,
        "candidate_count": len(candidates),
        "independent_critique_count": len(critiques),
        "decision": decision if decision in _DECISIONS else None,
        "runtime_id": runtime_id if isinstance(runtime_id, str) and runtime_id else None,
    }
