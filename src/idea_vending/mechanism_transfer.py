"""Deterministic cross-industry mechanism-transfer contract for v0.3 PR C."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

TRANSFER_KEYS = {
    "transfer_id",
    "source_domain",
    "mechanism_name",
    "mechanism_description",
    "source_constraint",
    "why_it_works_there",
    "target_equivalent_constraint",
    "transfer_logic",
    "value_chain_change",
    "expected_customer_value",
    "new_risks",
    "supporting_claim_ids",
}
_TRANSFER_ID_RE = re.compile(r"^transfer_[0-9a-f]{12}$")


def _text(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _unique_text_list(field: str, value: Any, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    normalized = [item.strip() for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


def _known_claim_ids(graph: dict[str, Any]) -> set[str]:
    if not isinstance(graph, dict) or not isinstance(graph.get("records"), list):
        raise ValueError("graph must be a valid Evidence Graph object")
    return {
        record.get("claim_id")
        for record in graph["records"]
        if isinstance(record, dict) and isinstance(record.get("claim_id"), str)
    }


def _stable_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"transfer_{hashlib.sha256(raw).hexdigest()[:12]}"


def create_mechanism_transfer(
    *,
    graph: dict[str, Any],
    source_domain: str,
    mechanism_name: str,
    mechanism_description: str,
    source_constraint: str,
    why_it_works_there: str,
    target_equivalent_constraint: str,
    transfer_logic: str,
    value_chain_change: str,
    expected_customer_value: str,
    new_risks: list[str],
    supporting_claim_ids: list[str],
) -> dict[str, Any]:
    """Create a validated causal mechanism transfer with a trusted stable ID."""
    payload = {
        "source_domain": _text("source_domain", source_domain),
        "mechanism_name": _text("mechanism_name", mechanism_name),
        "mechanism_description": _text("mechanism_description", mechanism_description),
        "source_constraint": _text("source_constraint", source_constraint),
        "why_it_works_there": _text("why_it_works_there", why_it_works_there),
        "target_equivalent_constraint": _text(
            "target_equivalent_constraint", target_equivalent_constraint
        ),
        "transfer_logic": _text("transfer_logic", transfer_logic),
        "value_chain_change": _text("value_chain_change", value_chain_change),
        "expected_customer_value": _text(
            "expected_customer_value", expected_customer_value
        ),
        "new_risks": _unique_text_list("new_risks", new_risks, allow_empty=False),
        "supporting_claim_ids": _unique_text_list(
            "supporting_claim_ids", supporting_claim_ids, allow_empty=True
        ),
    }
    unknown = sorted(set(payload["supporting_claim_ids"]) - _known_claim_ids(graph))
    if unknown:
        raise ValueError(f"unknown Evidence Graph claim IDs: {', '.join(unknown)}")
    record = {"transfer_id": _stable_id(payload), **payload}
    validate_mechanism_transfer(record, graph)
    return record


def validate_mechanism_transfer(record: dict[str, Any], graph: dict[str, Any]) -> None:
    """Validate causal fields, evidence refs, and the trusted content-addressed ID."""
    if not isinstance(record, dict) or set(record) != TRANSFER_KEYS:
        raise ValueError("mechanism transfer keys do not match the PR C contract")

    transfer_id = _text("transfer_id", record["transfer_id"])
    if not _TRANSFER_ID_RE.fullmatch(transfer_id):
        raise ValueError("transfer_id must be a trusted transfer_<12hex> identifier")

    payload = {}
    for field in (
        "source_domain",
        "mechanism_name",
        "mechanism_description",
        "source_constraint",
        "why_it_works_there",
        "target_equivalent_constraint",
        "transfer_logic",
        "value_chain_change",
        "expected_customer_value",
    ):
        payload[field] = _text(field, record[field])

    risks = _unique_text_list("new_risks", record["new_risks"], allow_empty=False)
    claims = _unique_text_list(
        "supporting_claim_ids", record["supporting_claim_ids"], allow_empty=True
    )
    payload["new_risks"] = risks
    payload["supporting_claim_ids"] = claims

    unknown = sorted(set(claims) - _known_claim_ids(graph))
    if unknown:
        raise ValueError(f"unknown Evidence Graph claim IDs: {', '.join(unknown)}")

    if _stable_id(payload) != transfer_id:
        raise ValueError("transfer_id does not match mechanism transfer content")
