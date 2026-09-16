"""Provider-neutral research-pass orchestration for Idea Vending Machine v0.3.

The engine accepts only normalized Evidence Records. Provider payloads and raw
research text are treated as untrusted data and are never executed.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from src.idea_vending.evidence_graph import (
    add_evidence_record,
    audit_evidence_coverage,
    validate_evidence_record,
)

RESEARCH_PASS_TYPES = {"landscape", "collision"}
RESEARCH_STATUSES = {"pending", "in_progress", "complete"}

_REQUEST_KEYS = {
    "research_id",
    "evolution_id",
    "pass_type",
    "question",
    "queries",
    "required_evidence_categories",
    "candidate_ids",
    "status",
    "evidence_ids",
    "provider_runs",
}

_RESEARCH_ID_RE = re.compile(r"^research_[A-Za-z0-9_-]{6,64}$")
_EVOLUTION_ID_RE = re.compile(r"^evo_[A-Za-z0-9_-]{8,64}$")
_EVIDENCE_ID_RE = re.compile(r"^ev_[A-Za-z0-9_-]{6,64}$")


def _non_empty_string_list(field: str, value: Any, *, allow_empty: bool = False) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} must not contain duplicates")


def validate_research_request(request: dict[str, Any]) -> None:
    """Validate the stable provider-neutral research request envelope."""
    if not isinstance(request, dict) or set(request) != _REQUEST_KEYS:
        raise ValueError("research request keys do not match the v0.3 contract")

    research_id = request["research_id"]
    if not isinstance(research_id, str) or not _RESEARCH_ID_RE.fullmatch(research_id):
        raise ValueError("research_id must match research_[A-Za-z0-9_-]{6,64}")

    evolution_id = request["evolution_id"]
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")

    pass_type = request["pass_type"]
    if pass_type not in RESEARCH_PASS_TYPES:
        raise ValueError(f"pass_type must be one of {sorted(RESEARCH_PASS_TYPES)}")

    question = request["question"]
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")

    _non_empty_string_list("queries", request["queries"])
    _non_empty_string_list(
        "required_evidence_categories", request["required_evidence_categories"]
    )
    _non_empty_string_list("candidate_ids", request["candidate_ids"], allow_empty=True)
    _non_empty_string_list("evidence_ids", request["evidence_ids"], allow_empty=True)

    for evidence_id in request["evidence_ids"]:
        if not _EVIDENCE_ID_RE.fullmatch(evidence_id):
            raise ValueError("evidence_ids must contain valid ev_ identifiers")

    categories = set(request["required_evidence_categories"])
    if pass_type == "landscape" and "counter_evidence" not in categories:
        raise ValueError("landscape research requires counter_evidence coverage")
    if pass_type == "collision":
        required = {"prior_art", "competitors", "failure_or_blockers"}
        missing = sorted(required - categories)
        if missing:
            raise ValueError(f"collision research is missing required categories: {missing}")

    if request["status"] not in RESEARCH_STATUSES:
        raise ValueError(f"status must be one of {sorted(RESEARCH_STATUSES)}")

    provider_runs = request["provider_runs"]
    if not isinstance(provider_runs, list):
        raise ValueError("provider_runs must be a list")
    for run in provider_runs:
        if not isinstance(run, dict) or set(run) != {
            "provider",
            "provider_run_id",
            "metadata",
            "evidence_ids",
        }:
            raise ValueError("provider_runs entries do not match the audit contract")
        for field in ("provider", "provider_run_id"):
            if not isinstance(run[field], str) or not run[field].strip():
                raise ValueError(f"provider_runs {field} must be a non-empty string")
        if not isinstance(run["metadata"], dict):
            raise ValueError("provider_runs metadata must be a dictionary")
        _non_empty_string_list("provider_runs evidence_ids", run["evidence_ids"])


def create_research_request(
    *,
    research_id: str,
    evolution_id: str,
    pass_type: str,
    question: str,
    queries: list[str],
    required_evidence_categories: list[str],
    candidate_ids: list[str],
) -> dict[str, Any]:
    """Create a deterministic provider-neutral research request."""
    request = {
        "research_id": research_id,
        "evolution_id": evolution_id,
        "pass_type": pass_type,
        "question": question,
        "queries": list(queries),
        "required_evidence_categories": list(required_evidence_categories),
        "candidate_ids": list(candidate_ids),
        "status": "pending",
        "evidence_ids": [],
        "provider_runs": [],
    }
    validate_research_request(request)
    return request


def _validate_provider_result(provider_result: dict[str, Any]) -> None:
    if not isinstance(provider_result, dict) or set(provider_result) != {
        "provider",
        "provider_run_id",
        "records",
        "metadata",
    }:
        raise ValueError("provider result does not match the normalized ingestion contract")
    for field in ("provider", "provider_run_id"):
        if not isinstance(provider_result[field], str) or not provider_result[field].strip():
            raise ValueError(f"provider result {field} must be a non-empty string")
    if not isinstance(provider_result["records"], list) or not provider_result["records"]:
        raise ValueError("provider result records must be a non-empty list")
    if not isinstance(provider_result["metadata"], dict):
        raise ValueError("provider result metadata must be a dictionary")


def ingest_provider_result(
    request: dict[str, Any], graph: dict[str, Any], provider_result: dict[str, Any]
) -> None:
    """Attach one provider run after every record passes Evidence Record validation."""
    validate_research_request(request)
    if not isinstance(graph, dict) or graph.get("evolution_id") != request["evolution_id"]:
        raise ValueError("evidence graph evolution_id must match the research request")
    _validate_provider_result(provider_result)

    normalized_records = []
    for record in provider_result["records"]:
        try:
            validate_evidence_record(record)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "provider records must be normalized Evidence Record objects"
            ) from exc
        normalized_records.append(record)

    ingested_ids = []
    for record in normalized_records:
        add_evidence_record(graph, record)
        evidence_id = record["evidence_id"]
        request["evidence_ids"].append(evidence_id)
        ingested_ids.append(evidence_id)

    request["provider_runs"].append(
        {
            "provider": provider_result["provider"],
            "provider_run_id": provider_result["provider_run_id"],
            "metadata": deepcopy(provider_result["metadata"]),
            "evidence_ids": ingested_ids,
        }
    )
    request["status"] = "in_progress"
    validate_research_request(request)


def complete_research_pass(
    request: dict[str, Any], graph: dict[str, Any]
) -> dict[str, Any]:
    """Close a research pass only after required evidence and counter-evidence exist."""
    validate_research_request(request)
    if not isinstance(graph, dict) or graph.get("evolution_id") != request["evolution_id"]:
        raise ValueError("evidence graph evolution_id must match the research request")
    records = graph.get("records")
    if not request["evidence_ids"] or not isinstance(records, list) or not records:
        raise ValueError("research pass cannot complete with zero evidence")

    graph_by_id = {record.get("evidence_id"): record for record in records if isinstance(record, dict)}
    linked = []
    for evidence_id in request["evidence_ids"]:
        record = graph_by_id.get(evidence_id)
        if record is None:
            raise ValueError(f"research request references unknown evidence_id: {evidence_id}")
        validate_evidence_record(record)
        linked.append(record)

    observed_categories = {record["evidence_type"] for record in linked}
    required_categories = set(request["required_evidence_categories"])
    missing_categories = sorted(required_categories - observed_categories)
    if missing_categories:
        raise ValueError(f"missing required evidence categories: {missing_categories}")

    if not any(record["supports_or_contradicts"] == "contradicts" for record in linked):
        raise ValueError("research pass requires explicit counter-evidence")

    request["status"] = "complete"
    validate_research_request(request)
    return audit_evidence_coverage(graph)
