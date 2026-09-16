"""Bounded in-memory storage for trusted completed evolution assessments."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import time
from typing import Any, Callable

from src.idea_vending.evidence_attachment import validate_state_evidence_against_graph
from src.idea_vending.evolution_schema import validate_complete_report
from src.idea_vending.runtime_schema import validate_runtime_record

_DOCUMENT_NAMES = {"spec.md", "design.md", "plan.md"}


class AssessmentStore:
    """Keep a bounded, expiring, defensive copy of completed assessments."""

    def __init__(
        self,
        max_entries: int = 32,
        ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(max_entries, int) or isinstance(max_entries, bool) or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        if (
            not isinstance(ttl_seconds, (int, float))
            or isinstance(ttl_seconds, bool)
            or ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be positive")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self._max_entries = max_entries
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _evict_expired_and_over_capacity(self) -> None:
        now = self._clock()
        expired = [
            runtime_id
            for runtime_id, record in self._records.items()
            if now - record["created_at"] > self._ttl_seconds
        ]
        for runtime_id in expired:
            self._records.pop(runtime_id, None)
        while len(self._records) > self._max_entries:
            self._records.popitem(last=False)

    def save_completed(self, result: dict[str, Any]) -> str:
        if not isinstance(result, dict):
            raise ValueError("result must be a dictionary")
        runtime = result.get("runtime")
        state = result.get("state")
        graph = result.get("evidence_graph")
        validate_runtime_record(runtime)
        if runtime["status"] != "completed":
            raise ValueError("only completed assessments can be stored")
        validate_complete_report(state)
        validate_state_evidence_against_graph(state, graph)
        if runtime["evolution_id"] != state["evolution_id"]:
            raise ValueError("runtime and state evolution_id must match")

        runtime_id = runtime["runtime_id"]
        self._records[runtime_id] = {
            "runtime_id": runtime_id,
            "evolution_id": runtime["evolution_id"],
            "result": deepcopy(result),
            "created_at": self._clock(),
            "approved": False,
            "approved_state": None,
            "documents": None,
        }
        self._records.move_to_end(runtime_id)
        self._evict_expired_and_over_capacity()
        return runtime_id

    def get(self, runtime_id: str) -> dict[str, Any] | None:
        if not isinstance(runtime_id, str) or not runtime_id.strip():
            return None
        self._evict_expired_and_over_capacity()
        record = self._records.get(runtime_id)
        return deepcopy(record) if record is not None else None

    def mark_approved(
        self,
        runtime_id: str,
        state: dict[str, Any],
        documents: dict[str, str],
    ) -> dict[str, Any]:
        self._evict_expired_and_over_capacity()
        record = self._records.get(runtime_id)
        if record is None:
            raise KeyError("assessment not found or expired")
        if record["approved"]:
            return deepcopy(record)

        validate_complete_report(state)
        expected_state = deepcopy(record["result"]["state"])
        expected_state["human_decision"] = "proceed"
        if state != expected_state:
            raise ValueError("approved state must equal trusted stored state plus human proceed")
        if state["decision"] not in {"GO", "MODIFY"}:
            raise ValueError("only GO or MODIFY can be approved")
        if not isinstance(documents, dict) or set(documents) != _DOCUMENT_NAMES:
            raise ValueError("documents must contain spec.md, design.md, and plan.md")
        if not all(isinstance(value, str) and value for value in documents.values()):
            raise ValueError("documents must contain non-empty text")

        record["approved"] = True
        record["approved_state"] = deepcopy(state)
        record["documents"] = deepcopy(documents)
        return deepcopy(record)
