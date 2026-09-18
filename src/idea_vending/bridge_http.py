"""Additive HTTP behavior for actionable Bridge validation failures.

The verified legacy handler remains the base implementation. This mixin only
overrides Forge/Judge import error presentation; success, replay, persistence,
Judge independence, deterministic decision authority, and approval semantics are
preserved.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from src.idea_vending.bridge_errors import bridge_import_error_payload
from src.idea_vending.bridge_runtime import (
    bridge_payload_digest,
    validate_and_finalize_judge_import,
    validate_and_run_forge_import,
)


MAX_BRIDGE_BODY_BYTES = 1024 * 1024


def _forge_import_response(record: dict[str, Any]) -> dict[str, Any]:
    trusted_forge = record.get("trusted_forge")
    candidates = trusted_forge.get("candidates", []) if isinstance(trusted_forge, dict) else []
    return {
        "bridge_session_id": record["bridge_session_id"],
        "state": record["state"],
        "candidate_count": len(candidates),
    }


def _completed_bridge_response(session_id: str, completed: dict[str, Any]) -> dict[str, Any]:
    response = deepcopy(completed)
    response["bridge_session_id"] = session_id
    return response


class BridgeValidationHTTPMixin:
    """Preserve Bridge transport while exposing only closed safe error metadata."""

    @staticmethod
    def _bridge_now_provider() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _handle_bridge_forge_import(self) -> None:
        envelope = self._read_json_object(max_body_bytes=MAX_BRIDGE_BODY_BYTES)
        if envelope is None:
            return
        try:
            digest = bridge_payload_digest(envelope)
            session_id = envelope["bridge_session_id"]
        except ValueError as exc:
            self._send_json(400, bridge_import_error_payload(str(exc)))
            return
        except (KeyError, TypeError):
            self._send_json(400, {"error": "bridge_import_invalid"})
            return

        store = self.server.bridge_store  # type: ignore[attr-defined]
        record = store.get(session_id)
        if record is None:
            self._send_json(404, {"error": "bridge_session_not_found_or_expired"})
            return

        existing_digest = record.get("forge_digest")
        if existing_digest is not None:
            if existing_digest != digest:
                self._send_json(409, {"error": "conflicting_forge_replay"})
                return
            self._send_json(200, _forge_import_response(record))
            return
        if record.get("state") != "forge_requested":
            self._send_json(409, {"error": "bridge_state_conflict"})
            return

        try:
            trusted_forge = validate_and_run_forge_import(
                record,
                envelope,
                now_provider=self._bridge_now_provider,
            )
            saved = store.save_forge(session_id, digest, trusted_forge)
        except ValueError as exc:
            code = str(exc)
            if code == "conflicting_forge_replay":
                self._send_json(409, {"error": code})
            elif code == "bridge_state_invalid":
                self._send_json(409, {"error": "bridge_state_conflict"})
            else:
                self._send_json(400, bridge_import_error_payload(code))
            return
        except Exception:
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(200, _forge_import_response(saved))

    def _handle_bridge_judge_import(self) -> None:
        envelope = self._read_json_object(max_body_bytes=MAX_BRIDGE_BODY_BYTES)
        if envelope is None:
            return
        try:
            digest = bridge_payload_digest(envelope)
            session_id = envelope["bridge_session_id"]
        except ValueError as exc:
            self._send_json(400, bridge_import_error_payload(str(exc)))
            return
        except (KeyError, TypeError):
            self._send_json(400, {"error": "bridge_import_invalid"})
            return

        bridge_store = self.server.bridge_store  # type: ignore[attr-defined]
        record = bridge_store.get(session_id)
        if record is None:
            self._send_json(404, {"error": "bridge_session_not_found_or_expired"})
            return

        existing_digest = record.get("judge_digest")
        if existing_digest is not None:
            if existing_digest != digest:
                self._send_json(409, {"error": "conflicting_judge_replay"})
                return
            completed = record.get("completed_result")
            if not isinstance(completed, dict):
                self._send_json(500, {"error": "bridge_runtime_failed"})
                return
            self._send_json(200, _completed_bridge_response(session_id, completed))
            return
        if record.get("state") != "judge_requested":
            self._send_json(409, {"error": "bridge_state_conflict"})
            return

        try:
            completed = validate_and_finalize_judge_import(
                record,
                envelope,
                now_provider=self._bridge_now_provider,
            )
            self.server.assessment_store.save_completed(completed)  # type: ignore[attr-defined]
            bridge_store.save_decision(session_id, digest, completed)
        except ValueError as exc:
            code = str(exc)
            if code == "conflicting_judge_replay":
                self._send_json(409, {"error": code})
            elif code == "bridge_state_invalid":
                self._send_json(409, {"error": "bridge_state_conflict"})
            else:
                self._send_json(400, bridge_import_error_payload(code))
            return
        except Exception:
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(200, _completed_bridge_response(session_id, completed))
