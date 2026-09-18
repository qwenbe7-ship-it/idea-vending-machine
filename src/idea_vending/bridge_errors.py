"""Safe, user-actionable Bridge validation errors.

Only closed, server-owned messages are exposed to clients. Raw exception text,
untrusted JSON values, provider output, credentials, and stack traces must never
be reflected by this module.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_VALIDATION_ERRORS: dict[str, dict[str, Any]] = {
    "bridge_forge_package_pasted_as_result": {
        "code": "bridge_forge_package_pasted_as_result",
        "path": None,
        "message": "실행용 Forge 패키지를 ChatGPT 결과 칸에 붙여넣었습니다.",
        "expected_rule": "Paste only the final seven-section JSON object returned by ChatGPT after running the Forge prompt",
        "actual_summary": None,
        "repair_instruction": (
            "‘ChatGPT에서 계속하기’를 눌러 새 ChatGPT 대화에 복사된 내용을 붙여넣고 실행한 뒤, "
            "ChatGPT가 최종으로 반환한 JSON object만 결과 칸에 붙여넣으세요."
        ),
    },
    "bridge_judge_package_pasted_as_result": {
        "code": "bridge_judge_package_pasted_as_result",
        "path": None,
        "message": "실행용 Judge 패키지를 독립 검증 결과 칸에 붙여넣었습니다.",
        "expected_rule": "Paste only the final Judge JSON object returned by the separate ChatGPT conversation",
        "actual_summary": None,
        "repair_instruction": (
            "Judge의 ‘ChatGPT에서 계속하기’를 눌러 별도의 새 ChatGPT 대화에서 실행한 뒤, "
            "그 대화가 반환한 최종 JSON object만 결과 칸에 붙여넣으세요."
        ),
    },
    "bridge_publication_date_invalid": {
        "code": "bridge_publication_date_invalid",
        "path": None,
        "message": "publication_date는 검증 가능한 YYYY-MM-DD 형식이어야 합니다.",
        "expected_rule": "YYYY-MM-DD",
        "actual_summary": None,
        "repair_instruction": (
            "정확한 게시일을 확인할 수 있는 출처를 사용하고 publication_date를 YYYY-MM-DD로 작성하세요. "
            "게시일을 검증할 수 없다면 그 출처를 admitted evidence에서 제외하세요."
        ),
    },
    "bridge_claim_reference_unknown": {
        "code": "bridge_claim_reference_unknown",
        "path": None,
        "message": "현재 Forge 단계에서 아직 사용할 수 없는 bridge_claim_ref가 참조되었습니다.",
        "expected_rule": (
            "extract_assumptions, discover_mechanisms, forge_candidates는 landscape_research에서 먼저 정의된 "
            "bridge_claim_ref만 참조할 수 있습니다."
        ),
        "actual_summary": None,
        "repair_instruction": (
            "해당 참조를 landscape_research의 기존 bridge_claim_ref로 교체하거나 제거하세요. "
            "collision_research에서 새로 정의되는 bc_ 참조는 이전 Forge 단계에서 사용하지 마세요."
        ),
    },
    "bridge_source_url_invalid": {
        "code": "bridge_source_url_invalid",
        "path": None,
        "message": "source_url은 유효한 http 또는 https URL이어야 합니다.",
        "expected_rule": "Absolute http:// or https:// URL",
        "actual_summary": None,
        "repair_instruction": "실제로 확인한 원문 출처의 유효한 http 또는 https URL로 교체하세요.",
    },
    "bridge_claim_ref_invalid": {
        "code": "bridge_claim_ref_invalid",
        "path": None,
        "message": "bridge_claim_ref 형식이 올바르지 않습니다.",
        "expected_rule": "bc_ prefix followed by 4-64 letters, digits, underscores, or hyphens",
        "actual_summary": None,
        "repair_instruction": "각 evidence draft에 고유한 bc_ 형식 참조값을 사용하세요.",
    },
    "bridge_claim_ref_duplicate": {
        "code": "bridge_claim_ref_duplicate",
        "path": None,
        "message": "동일한 bridge_claim_ref가 둘 이상의 evidence draft에 사용되었습니다.",
        "expected_rule": "Every evidence draft must have a unique bridge_claim_ref",
        "actual_summary": None,
        "repair_instruction": "중복된 evidence draft의 bridge_claim_ref를 각각 고유한 값으로 변경하세요.",
    },
    "bridge_claim_reference_invalid": {
        "code": "bridge_claim_reference_invalid",
        "path": None,
        "message": "claim reference 형식이 올바르지 않습니다.",
        "expected_rule": "Claim references must use valid bc_ bridge_claim_ref values",
        "actual_summary": None,
        "repair_instruction": "claim reference를 result_contract가 허용하는 bc_ 형식으로 수정하세요.",
    },
    "bridge_claim_reference_list_invalid": {
        "code": "bridge_claim_reference_list_invalid",
        "path": None,
        "message": "claim reference 필드는 배열이어야 합니다.",
        "expected_rule": "supporting_claim_ids / contradicting_claim_ids / evidence_claim_ids must be arrays",
        "actual_summary": None,
        "repair_instruction": "해당 claim reference 필드를 JSON 배열로 작성하세요.",
    },
    "bridge_landscape_candidate_families_invalid": {
        "code": "bridge_landscape_candidate_families_invalid",
        "path": None,
        "message": "landscape_research evidence는 특정 candidate family에 귀속될 수 없습니다.",
        "expected_rule": "landscape_research[].candidate_families must be []",
        "actual_summary": None,
        "repair_instruction": "landscape_research의 candidate_families 값을 빈 배열 []로 변경하세요.",
    },
    "bridge_candidate_family_unknown": {
        "code": "bridge_candidate_family_unknown",
        "path": None,
        "message": "허용되지 않은 candidate family가 사용되었습니다.",
        "expected_rule": "Use only candidate families supplied by candidate_family_contract",
        "actual_summary": None,
        "repair_instruction": "candidate_family_contract에 포함된 family 이름만 사용하세요.",
    },
    "bridge_market_size_invalid": {
        "code": "bridge_market_size_invalid",
        "path": None,
        "message": "market_size가 허용된 시장규모 계약을 만족하지 않습니다.",
        "expected_rule": "market_size must match the exported result_contract market_size schema",
        "actual_summary": None,
        "repair_instruction": "market_size 필드를 result_contract의 정확한 필드와 타입에 맞추거나, 근거가 없으면 null로 두세요.",
    },
    "bridge_evidence_draft_invalid": {
        "code": "bridge_evidence_draft_invalid",
        "path": None,
        "message": "evidence draft의 필드 구성이 result_contract와 일치하지 않습니다.",
        "expected_rule": "Evidence draft must contain exactly the fields declared by result_contract",
        "actual_summary": None,
        "repair_instruction": "빠진 필드를 추가하고 허용되지 않은 추가 필드를 제거하세요.",
    },
    "bridge_forge_result_invalid": {
        "code": "bridge_forge_result_invalid",
        "path": None,
        "message": "Forge 최종 JSON의 최상위 구조가 계약과 일치하지 않습니다.",
        "expected_rule": (
            "최상위에는 landscape_research, extract_assumptions, challenge_assumptions, "
            "propose_reframes, discover_mechanisms, forge_candidates, collision_research의 7개 key만 있어야 합니다."
        ),
        "actual_summary": None,
        "repair_instruction": "설명·summary·metadata 같은 추가 최상위 key를 제거하고 요구된 7개 section만 남기세요.",
    },
    "bridge_candidate_family_order_invalid": {
        "code": "bridge_candidate_family_order_invalid",
        "path": "forge_candidates.candidates",
        "message": "10개 candidate family의 순서가 서버의 canonical order와 다릅니다.",
        "expected_rule": "candidate_family_contract에 제공된 canonical order를 그대로 사용해야 합니다.",
        "actual_summary": None,
        "repair_instruction": "후보 내용을 바꾸지 말고 candidates 배열만 candidate_family_contract 순서로 다시 정렬하세요.",
    },
    "bridge_landscape_research_invalid": {
        "code": "bridge_landscape_research_invalid",
        "path": "landscape_research",
        "message": "landscape_research가 비어 있거나 배열 형식이 아닙니다.",
        "expected_rule": "landscape_research must be a non-empty array of evidence drafts",
        "actual_summary": None,
        "repair_instruction": "현재 시장/문제 근거와 counter-evidence를 포함한 evidence draft 배열을 반환하세요.",
    },
    "bridge_collision_research_invalid": {
        "code": "bridge_collision_research_invalid",
        "path": "collision_research",
        "message": "collision_research가 비어 있거나 배열 형식이 아닙니다.",
        "expected_rule": "collision_research must be a non-empty array",
        "actual_summary": None,
        "repair_instruction": "prior_art, competitors, failure_or_blockers를 포함한 collision evidence 배열을 반환하세요.",
    },
    "bridge_ideation_result_missing": {
        "code": "bridge_ideation_result_missing",
        "path": None,
        "message": "필수 Forge ideation section이 없거나 object 형식이 아닙니다.",
        "expected_rule": "Every required Forge ideation section must be present as an object",
        "actual_summary": None,
        "repair_instruction": "result_contract.required_top_level_keys와 section_schemas를 다시 따라 누락된 section을 복구하세요.",
    },
    "bridge_evidence_direction_invalid": {
        "code": "bridge_evidence_direction_invalid",
        "path": None,
        "message": "supports_or_contradicts 값이 허용된 enum이 아닙니다.",
        "expected_rule": "Use only the supports_or_contradicts values allowed by result_contract",
        "actual_summary": None,
        "repair_instruction": "result_contract의 enum 값 중 하나로 수정하세요.",
    },
    "bridge_confidence_tier_invalid": {
        "code": "bridge_confidence_tier_invalid",
        "path": None,
        "message": "confidence_tier 값이 허용된 enum이 아닙니다.",
        "expected_rule": "Use only confidence_tier values allowed by result_contract",
        "actual_summary": None,
        "repair_instruction": "result_contract의 confidence_tier enum 중 하나로 수정하세요.",
    },
    "bridge_freshness_status_invalid": {
        "code": "bridge_freshness_status_invalid",
        "path": None,
        "message": "freshness_status 값이 허용된 enum이 아닙니다.",
        "expected_rule": "Use only freshness_status values allowed by result_contract",
        "actual_summary": None,
        "repair_instruction": "result_contract의 freshness_status enum 중 하나로 수정하세요.",
    },
    "bridge_candidate_families_invalid": {
        "code": "bridge_candidate_families_invalid",
        "path": None,
        "message": "candidate_families가 문자열 배열 형식이 아닙니다.",
        "expected_rule": "candidate_families must be an array of canonical family names",
        "actual_summary": None,
        "repair_instruction": "candidate_families를 result_contract가 허용한 family 문자열 배열로 수정하세요.",
    },
    "bridge_candidate_families_duplicate": {
        "code": "bridge_candidate_families_duplicate",
        "path": None,
        "message": "candidate_families에 중복 값이 있습니다.",
        "expected_rule": "candidate_families entries must be unique",
        "actual_summary": None,
        "repair_instruction": "중복된 family를 제거하세요.",
    },
    "bridge_evidence_text_invalid": {
        "code": "bridge_evidence_text_invalid",
        "path": None,
        "message": "evidence의 notes 또는 raw_excerpt가 문자열 형식이 아닙니다.",
        "expected_rule": "notes and raw_excerpt must be strings",
        "actual_summary": None,
        "repair_instruction": "notes와 raw_excerpt를 문자열로 작성하세요. 내용이 없으면 빈 문자열을 사용하세요.",
    },
}


def safe_bridge_validation_error(code: str) -> dict[str, Any] | None:
    """Return closed, non-reflective validation metadata for Bridge contract failures."""
    if not isinstance(code, str):
        return None
    payload = _VALIDATION_ERRORS.get(code)
    if payload is not None:
        return deepcopy(payload)
    if code.startswith("bridge_"):
        return {
            "code": code,
            "path": None,
            "message": f"Bridge 결과가 서버 검증 계약을 통과하지 못했습니다. 오류 코드: {code}",
            "expected_rule": "Follow the exported result_contract exactly",
            "actual_summary": None,
            "repair_instruction": (
                "현재 ChatGPT 결과의 내용은 유지하되 result_contract의 exact keys, types, enums, "
                "reference rules, candidate count/order를 다시 맞춘 뒤 재검증하세요."
            ),
        }
    return {
        "code": "bridge_result_replay_contract_invalid",
        "path": None,
        "message": "Bridge 결과가 deterministic replay 단계의 내부 계약을 통과하지 못했습니다.",
        "expected_rule": "The imported result must satisfy every exported contract and trusted replay invariant",
        "actual_summary": None,
        "repair_instruction": (
            "같은 아이디어를 다시 조사할 필요는 없습니다. 현재 결과를 result_contract에 맞춰 구조만 교정한 뒤 재검증하세요."
        ),
    }


def bridge_import_error_payload(code: str) -> dict[str, Any]:
    """Preserve the legacy error while enriching only known safe failures."""
    payload: dict[str, Any] = {"error": "bridge_import_invalid"}
    validation_error = safe_bridge_validation_error(code)
    if validation_error is not None:
        payload["validation_error"] = validation_error
    return payload
