"""Deterministic Agent MD analyzer for raw product ideas."""

from __future__ import annotations

from typing import Any

_MIN_IDEA_LENGTH = 10

_AUTOMATION_KEYWORDS = {
    "자동": 2,
    "분류": 1,
    "추출": 1,
    "정리": 1,
    "분석": 1,
    "생성": 1,
    "검증": 1,
    "업로드": 1,
    "이메일": 1,
    "문서": 1,
}

_COMPLEXITY_KEYWORDS = {
    "실시간": 1,
    "결제": 1,
    "의료": 1,
    "법률": 1,
    "금융": 1,
    "예측": 1,
    "영상": 1,
    "음성": 1,
    "외부 시스템": 1,
}


def _normalize(idea: str) -> str:
    if not isinstance(idea, str):
        raise ValueError("idea must be a string")
    normalized = " ".join(idea.split())
    if len(normalized) < _MIN_IDEA_LENGTH:
        raise ValueError(f"idea must be at least {_MIN_IDEA_LENGTH} characters")
    return normalized


def _automation_level(idea: str) -> str:
    score = sum(weight for keyword, weight in _AUTOMATION_KEYWORDS.items() if keyword in idea)
    if score >= 6:
        return "A5"
    if score >= 4:
        return "A4"
    if score >= 3:
        return "A3"
    if score >= 2:
        return "A2"
    if score >= 1:
        return "A1"
    return "A0"


def _feasibility_level(idea: str) -> str:
    complexity = sum(weight for keyword, weight in _COMPLEXITY_KEYWORDS.items() if keyword in idea)
    if complexity == 0:
        return "T5"
    if complexity == 1:
        return "T4"
    if complexity == 2:
        return "T3"
    if complexity == 3:
        return "T2"
    return "T1"


def _infer_customer(idea: str) -> str:
    mappings = (
        (("부동산", "계약서"), "부동산 실무자·중개업자·계약 검토가 필요한 고객"),
        (("고객 문의", "이메일"), "반복 고객 문의를 처리하는 소규모 사업자와 운영팀"),
        (("영수증", "세금계산서"), "문서 입력 업무가 많은 소규모 사업자와 회계 담당자"),
        (("수업", "학생"), "교육 서비스 운영자와 학습자"),
    )
    for keywords, customer in mappings:
        if any(keyword in idea for keyword in keywords):
            return customer
    return "반복적인 정보 처리 업무를 줄이고 싶은 개인 또는 소규모 사업자"


def _risks(idea: str) -> list[str]:
    risks = ["입력 데이터의 형식과 품질이 일정하지 않을 수 있음"]
    if any(keyword in idea for keyword in ("계약", "법률", "의료", "금융")):
        risks.append("고위험 판단은 자동 확정하지 않고 사람의 최종 확인이 필요함")
    if any(keyword in idea for keyword in ("개인정보", "고객", "계약서", "영수증", "이메일")):
        risks.append("개인정보·민감정보 저장 범위와 접근권한을 최소화해야 함")
    risks.append("AI 판단을 사용하는 경우 오탐·누락을 검출할 검증 규칙이 필요함")
    return risks


def analyze_idea(idea: str) -> dict[str, Any]:
    """Turn a raw idea into a deterministic, development-oriented analysis."""
    normalized = _normalize(idea)
    automation_level = _automation_level(normalized)
    feasibility_level = _feasibility_level(normalized)

    return {
        "problem": f"현재 사람이 반복해서 처리하는 '{normalized}' 관련 업무를 더 빠르고 일관되게 처리할 필요가 있음",
        "customer": _infer_customer(normalized),
        "automation_level": automation_level,
        "feasibility_level": feasibility_level,
        "risks": _risks(normalized),
        "mvp_scope": [
            "사용자가 핵심 입력을 제출한다",
            "입력을 구조화하고 필요한 판단을 수행한다",
            "결과와 근거를 사람이 검토할 수 있는 형태로 반환한다",
            "실패·불확실 상태를 성공 결과와 명확히 구분한다",
        ],
        "acceptance_criteria": [
            "대표 정상 입력에서 구조화된 결과가 재현 가능하게 생성된다",
            "잘못되거나 부족한 입력은 성공으로 처리하지 않고 명확히 거부된다",
            "핵심 결과 필드가 누락되지 않으며 사람이 검토할 수 있다",
            "자동 검증 명령이 실패하면 릴리스가 차단된다",
        ],
    }
