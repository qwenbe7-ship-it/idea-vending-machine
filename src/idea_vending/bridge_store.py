"""Thread-safe bounded in-memory state for ChatGPT Plus bridge sessions."""

from __future__ import annotations

import secrets
import time
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from typing import Any, Callable


class BridgeStore:
    def __init__(
        self,
        *,
        max_entries: int = 16,
        ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self._max_entries = max_entries
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = RLock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            session_id
            for session_id, record in self._records.items()
            if now >= record["expires_at"]
        ]
        for session_id in expired:
            self._records.pop(session_id, None)

    def _record(self, session_id: str) -> dict[str, Any]:
        now = self._clock()
        self._purge_expired(now)
        record = self._records.get(session_id)
        if record is None:
            raise ValueError("bridge_session_not_found")
        self._records.move_to_end(session_id)
        return record

    def create(self, raw_idea: str) -> dict[str, Any]:
        if not isinstance(raw_idea, str) or not raw_idea.strip():
            raise ValueError("raw_idea must be a non-empty string")
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            while True:
                session_id = "br_" + secrets.token_urlsafe(18)
                if session_id not in self._records:
                    break
            record = {
                "bridge_session_id": session_id,
                "raw_idea": raw_idea,
                "state": "forge_requested",
                "created_at": now,
                "expires_at": now + self._ttl_seconds,
                "forge_digest": None,
                "trusted_forge": None,
                "judge_digest": None,
                "completed_result": None,
            }
            self._records[session_id] = record
            self._records.move_to_end(session_id)
            while len(self._records) > self._max_entries:
                self._records.popitem(last=False)
            return deepcopy(record)

    def get(self, session_id: str) -> dict[str, Any] | None:
        if not isinstance(session_id, str) or not session_id:
            return None
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            record = self._records.get(session_id)
            if record is None:
                return None
            self._records.move_to_end(session_id)
            return deepcopy(record)

    def save_forge(
        self,
        session_id: str,
        payload_digest: str,
        trusted_forge: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload_digest, str) or not payload_digest:
            raise ValueError("forge_digest_invalid")
        if not isinstance(trusted_forge, dict):
            raise ValueError("trusted_forge_invalid")
        with self._lock:
            record = self._record(session_id)
            existing = record["forge_digest"]
            if existing is not None:
                if existing != payload_digest:
                    raise ValueError("conflicting_forge_replay")
                return deepcopy(record)
            if record["state"] != "forge_requested":
                raise ValueError("bridge_state_invalid")
            record["forge_digest"] = payload_digest
            record["trusted_forge"] = deepcopy(trusted_forge)
            record["state"] = "forge_validated"
            return deepcopy(record)

    def mark_judge_requested(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._record(session_id)
            if record["state"] in {"judge_requested", "decision_ready", "approved", "blocked"}:
                return deepcopy(record)
            if record["state"] != "forge_validated":
                raise ValueError("bridge_state_invalid")
            record["state"] = "judge_requested"
            return deepcopy(record)

    def save_decision(
        self,
        session_id: str,
        payload_digest: str,
        completed_result: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload_digest, str) or not payload_digest:
            raise ValueError("judge_digest_invalid")
        if not isinstance(completed_result, dict):
            raise ValueError("completed_result_invalid")
        with self._lock:
            record = self._record(session_id)
            existing = record["judge_digest"]
            if existing is not None:
                if existing != payload_digest:
                    raise ValueError("conflicting_judge_replay")
                return deepcopy(record)
            if record["state"] != "judge_requested":
                raise ValueError("bridge_state_invalid")
            record["judge_digest"] = payload_digest
            record["completed_result"] = deepcopy(completed_result)
            record["state"] = "decision_ready"
            return deepcopy(record)
