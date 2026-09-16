"""Strict, provider-neutral contracts for the human-mediated ChatGPT Plus bridge."""

from __future__ import annotations

import math
import re
from typing import Any

BRIDGE_VERSION = "ivm-bridge-v1"
MAX_BRIDGE_JSON_DEPTH = 12
MAX_BRIDGE_COLLECTION_ITEMS = 256
MAX_BRIDGE_STRING_CHARS = 32_768

_SESSION_ID_RE = re.compile(r"^br_[A-Za-z0-9_-]{16,128}$")
_ENVELOPE_KEYS = {"bridge_session_id", "bridge_version", "result"}


def validate_bridge_json(value: Any, *, _depth: int = 0) -> None:
    """Bound untrusted JSON complexity before any domain-level validation."""
    if _depth > MAX_BRIDGE_JSON_DEPTH:
        raise ValueError("bridge_json_too_deep")
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("bridge_number_invalid")
        return
    if isinstance(value, str):
        if len(value) > MAX_BRIDGE_STRING_CHARS:
            raise ValueError("bridge_string_too_long")
        return
    if isinstance(value, list):
        if len(value) > MAX_BRIDGE_COLLECTION_ITEMS:
            raise ValueError("bridge_collection_too_large")
        for item in value:
            validate_bridge_json(item, _depth=_depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_BRIDGE_COLLECTION_ITEMS:
            raise ValueError("bridge_collection_too_large")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("bridge_json_type_invalid")
            if len(key) > MAX_BRIDGE_STRING_CHARS:
                raise ValueError("bridge_string_too_long")
            validate_bridge_json(item, _depth=_depth + 1)
        return
    raise ValueError("bridge_json_type_invalid")


def validate_bridge_envelope(envelope: Any) -> None:
    """Validate the exact Forge/Judge import envelope without trusting its result."""
    if not isinstance(envelope, dict) or set(envelope) != _ENVELOPE_KEYS:
        raise ValueError("bridge_envelope_invalid")
    validate_bridge_json(envelope)
    session_id = envelope["bridge_session_id"]
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("bridge_session_id_invalid")
    if envelope["bridge_version"] != BRIDGE_VERSION:
        raise ValueError("bridge_version_mismatch")
    if not isinstance(envelope["result"], dict):
        raise ValueError("bridge_result_invalid")
