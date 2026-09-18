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
}


def safe_bridge_validation_error(code: str) -> dict[str, Any] | None:
    """Return a defensive copy for a known safe validation code, else None."""
    if not isinstance(code, str):
        return None
    payload = _VALIDATION_ERRORS.get(code)
    return deepcopy(payload) if payload is not None else None


def bridge_import_error_payload(code: str) -> dict[str, Any]:
    """Preserve the legacy error while enriching only known safe failures."""
    payload: dict[str, Any] = {"error": "bridge_import_invalid"}
    validation_error = safe_bridge_validation_error(code)
    if validation_error is not None:
        payload["validation_error"] = validation_error
    return payload
