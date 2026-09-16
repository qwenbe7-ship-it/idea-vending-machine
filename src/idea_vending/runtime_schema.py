"""Deterministic execution-state contract for Idea Vending Machine v0.3 PR E1."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any

RUNTIME_STATUSES = {"pending", "running", "completed", "incomplete", "failed"}
RUNTIME_STAGES = {
    "capture",
    "landscape_research",
    "assumption_analysis",
    "reframing",
    "mechanism_transfer",
    "candidate_forge",
    "collision_research",
    "independent_evaluation",
    "decision",
    "report_assembly",
}
EVENT_STATUSES = {"started", "completed", "blocked", "failed"}
PROVIDER_ROLES = {"research", "ideation", "evaluation"}
PROVIDER_RUN_STATUSES = {"completed", "incomplete", "failed"}
FAILURE_CODES = {
    "provider_not_configured",
    "provider_auth_failed",
    "provider_rate_limited",
    "provider_timeout",
    "provider_http_error",
    "provider_invalid_json",
    "provider_schema_mismatch",
    "research_insufficient",
    "research_source_metadata_insufficient",
    "candidate_admission_blocked",
    "collision_research_incomplete",
    "evaluator_unavailable",
    "internal_contract_violation",
}

_RUNTIME_KEYS = {
    "runtime_id",
    "evolution_id",
    "status",
    "current_stage",
    "stage_events",
    "provider_runs",
    "failure",
    "started_at",
    "completed_at",
}
_EVENT_KEYS = {
    "runtime_id",
    "evolution_id",
    "sequence",
    "stage",
    "status",
    "message_code",
    "occurred_at",
}
_PROVIDER_RUN_KEYS = {
    "provider",
    "provider_response_id",
    "role",
    "model",
    "operation",
    "started_at",
    "completed_at",
    "status",
    "usage",
    "source_count",
}
_FAILURE_KEYS = {"code", "stage"}

_RUNTIME_ID_RE = re.compile(r"^run_[A-Za-z0-9_-]{8,64}$")
_EVOLUTION_ID_RE = re.compile(r"^evo_[A-Za-z0-9_-]{8,64}$")


def _require_text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_timestamp(field: str, value: Any) -> None:
    _require_text(field, value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone offset")


def _validate_event(event: dict[str, Any], runtime: dict[str, Any], expected_sequence: int) -> None:
    if not isinstance(event, dict) or set(event) != _EVENT_KEYS:
        raise ValueError("stage event keys do not match the runtime contract")
    if event["runtime_id"] != runtime["runtime_id"]:
        raise ValueError("stage event runtime_id mismatch")
    if event["evolution_id"] != runtime["evolution_id"]:
        raise ValueError("stage event evolution_id mismatch")
    if event["sequence"] != expected_sequence:
        raise ValueError("stage event sequence must be monotonic")
    if event["stage"] not in RUNTIME_STAGES:
        raise ValueError("stage event stage is invalid")
    if event["status"] not in EVENT_STATUSES:
        raise ValueError("stage event status is invalid")
    _require_text("message_code", event["message_code"])
    _validate_timestamp("occurred_at", event["occurred_at"])


def _validate_provider_run(run: dict[str, Any]) -> None:
    if not isinstance(run, dict) or set(run) != _PROVIDER_RUN_KEYS:
        raise ValueError("provider run keys do not match the runtime contract")
    for field in ("provider", "provider_response_id", "model", "operation"):
        _require_text(field, run[field])
    if run["role"] not in PROVIDER_ROLES:
        raise ValueError("provider run role is invalid")
    if run["status"] not in PROVIDER_RUN_STATUSES:
        raise ValueError("provider run status is invalid")
    _validate_timestamp("provider run started_at", run["started_at"])
    _validate_timestamp("provider run completed_at", run["completed_at"])
    if not isinstance(run["usage"], dict):
        raise ValueError("provider run usage must be a dictionary")
    source_count = run["source_count"]
    if source_count is not None and (
        not isinstance(source_count, int) or isinstance(source_count, bool) or source_count < 0
    ):
        raise ValueError("provider run source_count must be a non-negative integer or null")


def validate_runtime_record(runtime: dict[str, Any]) -> None:
    """Validate one operational runtime record without adding business semantics."""
    if not isinstance(runtime, dict) or set(runtime) != _RUNTIME_KEYS:
        raise ValueError("runtime record keys do not match the PR E1 contract")

    runtime_id = runtime["runtime_id"]
    if not isinstance(runtime_id, str) or not _RUNTIME_ID_RE.fullmatch(runtime_id):
        raise ValueError("runtime_id must match run_[A-Za-z0-9_-]{8,64}")
    evolution_id = runtime["evolution_id"]
    if not isinstance(evolution_id, str) or not _EVOLUTION_ID_RE.fullmatch(evolution_id):
        raise ValueError("evolution_id must match evo_[A-Za-z0-9_-]{8,64}")
    if runtime["status"] not in RUNTIME_STATUSES:
        raise ValueError("runtime status is invalid")
    if runtime["current_stage"] is not None and runtime["current_stage"] not in RUNTIME_STAGES:
        raise ValueError("runtime current_stage is invalid")
    _validate_timestamp("started_at", runtime["started_at"])

    events = runtime["stage_events"]
    if not isinstance(events, list):
        raise ValueError("stage_events must be a list")
    for sequence, event in enumerate(events, start=1):
        _validate_event(event, runtime, sequence)

    runs = runtime["provider_runs"]
    if not isinstance(runs, list):
        raise ValueError("provider_runs must be a list")
    for run in runs:
        _validate_provider_run(run)

    failure = runtime["failure"]
    if failure is not None:
        if not isinstance(failure, dict) or set(failure) != _FAILURE_KEYS:
            raise ValueError("runtime failure keys do not match the PR E1 contract")
        if failure["code"] not in FAILURE_CODES:
            raise ValueError("runtime failure code is invalid")
        if failure["stage"] not in RUNTIME_STAGES:
            raise ValueError("runtime failure stage is invalid")

    terminal = runtime["status"] in {"completed", "incomplete", "failed"}
    if terminal:
        if runtime["completed_at"] is None:
            raise ValueError("terminal runtime must have completed_at")
        _validate_timestamp("completed_at", runtime["completed_at"])
    elif runtime["completed_at"] is not None:
        raise ValueError("non-terminal runtime cannot have completed_at")

    if runtime["status"] == "completed" and failure is not None:
        raise ValueError("completed runtime cannot have a failure")
    if runtime["status"] in {"incomplete", "failed"} and failure is None:
        raise ValueError("incomplete or failed runtime requires failure metadata")
    if runtime["status"] == "failed" and failure is not None:
        if failure["code"] != "internal_contract_violation":
            raise ValueError("failed runtime is reserved for internal_contract_violation")


def create_runtime_record(runtime_id: str, evolution_id: str, started_at: str) -> dict[str, Any]:
    runtime = {
        "runtime_id": runtime_id,
        "evolution_id": evolution_id,
        "status": "pending",
        "current_stage": None,
        "stage_events": [],
        "provider_runs": [],
        "failure": None,
        "started_at": started_at,
        "completed_at": None,
    }
    validate_runtime_record(runtime)
    return runtime


def append_stage_event(
    runtime: dict[str, Any],
    *,
    stage: str,
    status: str,
    message_code: str,
    occurred_at: str,
) -> None:
    validate_runtime_record(runtime)
    if runtime["status"] in {"completed", "incomplete", "failed"}:
        raise ValueError("cannot append a stage event to a terminal runtime")
    if stage not in RUNTIME_STAGES:
        raise ValueError("stage is invalid")
    if status not in EVENT_STATUSES:
        raise ValueError("event status is invalid")
    event = {
        "runtime_id": runtime["runtime_id"],
        "evolution_id": runtime["evolution_id"],
        "sequence": len(runtime["stage_events"]) + 1,
        "stage": stage,
        "status": status,
        "message_code": message_code,
        "occurred_at": occurred_at,
    }
    runtime["stage_events"].append(event)
    runtime["current_stage"] = stage
    runtime["status"] = "running"
    validate_runtime_record(runtime)


def record_provider_run(runtime: dict[str, Any], run: dict[str, Any]) -> None:
    validate_runtime_record(runtime)
    _validate_provider_run(run)
    runtime["provider_runs"].append(deepcopy(run))
    validate_runtime_record(runtime)


def _mark_terminal(
    runtime: dict[str, Any], *, status: str, code: str | None, stage: str | None, occurred_at: str
) -> None:
    validate_runtime_record(runtime)
    if runtime["status"] in {"completed", "incomplete", "failed"}:
        raise ValueError("runtime is already terminal")
    if status == "completed":
        runtime["failure"] = None
    else:
        if code not in FAILURE_CODES:
            raise ValueError("runtime failure code is invalid")
        if stage not in RUNTIME_STAGES:
            raise ValueError("runtime failure stage is invalid")
        if status == "failed" and code != "internal_contract_violation":
            raise ValueError("failed runtime is reserved for internal_contract_violation")
        runtime["failure"] = {"code": code, "stage": stage}
        runtime["current_stage"] = stage
    runtime["status"] = status
    runtime["completed_at"] = occurred_at
    validate_runtime_record(runtime)


def mark_runtime_incomplete(
    runtime: dict[str, Any], *, code: str, stage: str, occurred_at: str
) -> None:
    if code == "internal_contract_violation":
        raise ValueError("internal_contract_violation must use failed status")
    _mark_terminal(runtime, status="incomplete", code=code, stage=stage, occurred_at=occurred_at)


def mark_runtime_failed(runtime: dict[str, Any], *, code: str, stage: str, occurred_at: str) -> None:
    _mark_terminal(runtime, status="failed", code=code, stage=stage, occurred_at=occurred_at)


def mark_runtime_completed(runtime: dict[str, Any], *, occurred_at: str) -> None:
    _mark_terminal(runtime, status="completed", code=None, stage=None, occurred_at=occurred_at)
