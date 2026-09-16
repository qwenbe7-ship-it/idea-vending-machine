"""Replay untrusted ChatGPT bridge output through existing provider-neutral contracts."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Callable

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evidence_graph import create_evidence_record

_BRIDGE_REF_RE = re.compile(r"^bc_[A-Za-z0-9_-]{4,64}$")
_EVIDENCE_DRAFT_KEYS = {
    "bridge_claim_ref",
    "claim",
    "source_title",
    "source_url",
    "publisher",
    "publication_date",
    "geography",
    "population_or_market_definition",
    "evidence_type",
    "supports_or_contradicts",
    "confidence_tier",
    "freshness_status",
    "candidate_families",
    "notes",
    "raw_excerpt",
    "market_size",
}
_CLAIM_REFERENCE_KEYS = {
    "supporting_claim_ids",
    "contradicting_claim_ids",
    "evidence_claim_ids",
}


def _stable_id(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return prefix + hashlib.sha256(raw).hexdigest()[:16]


def _remap_claim_refs(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_remap_claim_refs(item, mapping) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in _CLAIM_REFERENCE_KEYS:
            if not isinstance(item, list):
                raise ValueError("bridge_claim_reference_list_invalid")
            mapped: list[str] = []
            for ref in item:
                if not isinstance(ref, str) or ref not in mapping:
                    raise ValueError("bridge_claim_reference_unknown")
                mapped.append(mapping[ref])
            result[key] = mapped
        else:
            result[key] = _remap_claim_refs(item, mapping)
    return result


def _remap_judge_claim_refs(value: Any, mapping: dict[str, str]) -> Any:
    """Map Judge-only bc_ references while preserving already-trusted claim_ references."""
    if isinstance(value, list):
        return [_remap_judge_claim_refs(item, mapping) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in _CLAIM_REFERENCE_KEYS:
            if not isinstance(item, list):
                raise ValueError("bridge_claim_reference_list_invalid")
            mapped: list[str] = []
            for ref in item:
                if not isinstance(ref, str):
                    raise ValueError("bridge_claim_reference_unknown")
                if ref.startswith("bc_"):
                    if ref not in mapping:
                        raise ValueError("bridge_claim_reference_unknown")
                    mapped.append(mapping[ref])
                else:
                    mapped.append(ref)
            result[key] = mapped
        else:
            result[key] = _remap_judge_claim_refs(item, mapping)
    return result


class BridgeResearchReplay:
    def __init__(
        self,
        forge_result: dict[str, Any],
        *,
        session_id: str,
        retrieved_date_provider: Callable[[], str],
    ) -> None:
        self._result = deepcopy(forge_result)
        self._session_id = session_id
        self._retrieved_date_provider = retrieved_date_provider
        self.claim_ref_map: dict[str, str] = {}
        self._candidate_family_order: list[str] = []
        self._additional_collision_evidence: list[dict[str, Any]] = []
        self.last_run_metadata: dict[str, Any] | None = None
        self._sequence = 0

    def set_candidate_family_order(self, families: list[str]) -> None:
        if len(families) != 10 or set(families) != CANDIDATE_FAMILIES:
            raise ValueError("bridge_candidate_family_coverage_invalid")
        if len(families) != len(set(families)):
            raise ValueError("bridge_candidate_family_duplicate")
        self._candidate_family_order = list(families)

    def set_additional_collision_evidence(self, drafts: list[dict[str, Any]]) -> None:
        if not isinstance(drafts, list):
            raise ValueError("bridge_additional_evidence_invalid")
        self._additional_collision_evidence = deepcopy(drafts)

    def _normalize_record(
        self,
        draft: Any,
        *,
        candidate_ids: list[str],
    ) -> dict[str, Any]:
        if not isinstance(draft, dict) or set(draft) != _EVIDENCE_DRAFT_KEYS:
            raise ValueError("bridge_evidence_draft_invalid")
        ref = draft["bridge_claim_ref"]
        if not isinstance(ref, str) or not _BRIDGE_REF_RE.fullmatch(ref):
            raise ValueError("bridge_claim_ref_invalid")
        if ref in self.claim_ref_map:
            raise ValueError("bridge_claim_ref_duplicate")
        families = draft["candidate_families"]
        if not isinstance(families, list) or any(not isinstance(item, str) for item in families):
            raise ValueError("bridge_candidate_families_invalid")

        mapped_candidate_ids: list[str] = []
        if families:
            if not self._candidate_family_order or len(candidate_ids) != len(self._candidate_family_order):
                raise ValueError("bridge_candidate_mapping_unavailable")
            family_to_id = dict(zip(self._candidate_family_order, candidate_ids))
            if not set(families).issubset(CANDIDATE_FAMILIES):
                raise ValueError("bridge_candidate_family_unknown")
            mapped_candidate_ids = [family_to_id[family] for family in families]

        claim_id = _stable_id(
            "claim_",
            {
                "session": self._session_id,
                "ref": ref,
                "claim": draft["claim"],
                "source_url": draft["source_url"],
            },
        )
        evidence_id = _stable_id(
            "ev_",
            {
                "session": self._session_id,
                "ref": ref,
                "publication_date": draft["publication_date"],
                "claim_id": claim_id,
            },
        )
        retrieved_at = self._retrieved_date_provider()
        record = create_evidence_record(
            evidence_id=evidence_id,
            claim_id=claim_id,
            claim=draft["claim"],
            source_title=draft["source_title"],
            source_url=draft["source_url"],
            publisher=draft["publisher"],
            publication_date=draft["publication_date"],
            retrieved_at=retrieved_at,
            geography=draft["geography"],
            population_or_market_definition=draft["population_or_market_definition"],
            evidence_type=draft["evidence_type"],
            supports_or_contradicts=draft["supports_or_contradicts"],
            confidence_tier=draft["confidence_tier"],
            freshness_status=draft["freshness_status"],
            candidate_ids=mapped_candidate_ids,
            notes=draft["notes"],
            raw_content_untrusted=draft["raw_excerpt"],
            provider_metadata={
                "provider": "chatgpt_plus_bridge",
                "source_verification": "user_mediated",
                "bridge_session_id": self._session_id,
            },
            market_size=draft["market_size"],
        )
        self.claim_ref_map[ref] = claim_id
        return record

    def research(self, request: dict[str, Any]) -> dict[str, Any]:
        pass_type = request.get("pass_type")
        if pass_type == "landscape":
            # A finalization replay begins with a fresh landscape pass. Reset only
            # transient ID mappings so the same trusted Forge artifact can be replayed.
            self.claim_ref_map = {}
            self._candidate_family_order = []
            drafts = self._result.get("landscape_research")
            candidate_ids: list[str] = []
        elif pass_type == "collision":
            base_drafts = self._result.get("collision_research")
            if not isinstance(base_drafts, list):
                raise ValueError("bridge_research_records_missing")
            drafts = [*deepcopy(base_drafts), *deepcopy(self._additional_collision_evidence)]
            candidate_ids = list(request.get("candidate_ids", []))
        else:
            raise ValueError("bridge_research_pass_invalid")
        if not isinstance(drafts, list) or not drafts:
            raise ValueError("bridge_research_records_missing")
        records = [self._normalize_record(draft, candidate_ids=candidate_ids) for draft in drafts]
        self._sequence += 1
        run_id = f"bridge_research_{self._sequence}"
        self.last_run_metadata = {
            "provider": "chatgpt_plus_bridge",
            "provider_response_id": run_id,
            "model": "user_chatgpt_plus",
            "operation": pass_type,
            "usage": {},
            "source_count": len(records),
        }
        return {
            "provider": "chatgpt_plus_bridge",
            "provider_run_id": run_id,
            "records": records,
            "metadata": {"source_count": len(records), "source_verification": "user_mediated"},
        }


class BridgeIdeationReplay:
    def __init__(self, forge_result: dict[str, Any], research_replay: BridgeResearchReplay) -> None:
        self._result = deepcopy(forge_result)
        self._research = research_replay
        self.last_run_metadata: dict[str, Any] | None = None
        self._sequence = 0

    def generate(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("operation")
        if operation not in {
            "extract_assumptions",
            "challenge_assumptions",
            "propose_reframes",
            "discover_mechanisms",
            "forge_candidates",
        }:
            raise ValueError("bridge_ideation_operation_invalid")
        raw = self._result.get(operation)
        if not isinstance(raw, dict):
            raise ValueError("bridge_ideation_result_missing")
        remapped = _remap_claim_refs(raw, self._research.claim_ref_map)
        if operation == "forge_candidates":
            candidates = remapped.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError("bridge_candidates_invalid")
            families = [item.get("family") for item in candidates if isinstance(item, dict)]
            self._research.set_candidate_family_order(families)
        self._sequence += 1
        self.last_run_metadata = {
            "provider": "chatgpt_plus_bridge",
            "provider_response_id": f"bridge_ideation_{self._sequence}",
            "model": "user_chatgpt_plus",
            "operation": operation,
            "usage": {},
            "source_count": None,
        }
        return remapped


class BridgeEvaluationReplay:
    """Expose imported Judge critiques as one provider-neutral evaluation call."""

    def __init__(self, judge_result: dict[str, Any], research_replay: BridgeResearchReplay) -> None:
        self._result = deepcopy(judge_result)
        self._research = research_replay
        self.last_run_metadata: dict[str, Any] | None = None

    def evaluate(self, request: dict[str, Any]) -> dict[str, Any]:
        critiques = self._result.get("critiques")
        if not isinstance(critiques, list):
            raise ValueError("bridge_judge_critiques_invalid")
        remapped = _remap_judge_claim_refs(
            {"critiques": critiques},
            self._research.claim_ref_map,
        )
        self.last_run_metadata = {
            "provider": "chatgpt_plus_bridge",
            "provider_response_id": "bridge_judge_import",
            "model": "user_chatgpt_plus_fresh_conversation",
            "operation": "independent_evaluation",
            "usage": {},
            "source_count": len(self._result.get("additional_evidence", [])),
        }
        return remapped
