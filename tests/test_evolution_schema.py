import unittest

from src.idea_vending.evolution_schema import (
    DETAIL_SECTION_KEYS,
    create_evolution_state,
    validate_complete_report,
    validate_detailed_analysis,
    validate_evolution_state,
    validate_executive_brief,
)


def make_complete_state():
    state = create_evolution_state(
        "고객 문의를 AI가 분류하고 답변 초안을 만드는 시스템",
        "evo_report001",
    )
    state["report_status"] = "complete"
    state["decision"] = "MODIFY"
    state["confidence"] = "medium"
    state["evolved_idea"] = "고객 문의를 사전에 예측하고 자동 처리하는 운영 의사결정 시스템"
    state["human_decision"] = "proceed"
    state["selected_concept_id"] = "candidate-category-shift"
    state["evidence_refs"] = ["claim-market-1", "claim-market-2", "claim-risk-1"]
    state["executive_brief"] = {
        "thesis": "단순 답변 초안보다 문의 발생 자체를 줄이는 운영 시스템으로 확장할 가치가 있다.",
        "why_now": "AI 자동화와 고객지원 운영 데이터가 동시에 축적되고 있다.",
        "evolution_delta": "사후 답변 작성에서 사전 예방과 운영 자동화로 이동한다.",
        "market_snapshot": {
            "stage": "early scale",
            "current_market": [
                {"label": "direct support automation market", "evidence_refs": ["claim-market-1"]}
            ],
            "forecast_market": [
                {"label": "forecast support automation market", "evidence_refs": ["claim-market-2"]}
            ],
            "growth": [],
            "buyer": "반복 고객 문의 비용이 큰 운영 책임자",
        },
        "best_customer": "반복 문의량이 많고 응답 SLA가 중요한 중소기업 운영팀",
        "business_value": "지원 인건비와 응답 지연을 줄이고 반복 문의의 원인을 제거한다.",
        "reasons_for": ["반복비용 절감", "자동화 가능성", "운영 데이터 축적"],
        "reasons_against": ["데이터 품질", "오답 위험", "기존 도구 경쟁"],
        "critical_unknowns": ["실제 구매자가 사전 예방 기능에 추가 비용을 지불하는가"],
        "cheapest_next_validation": {
            "action": "잠재 고객 5곳의 최근 문의 100건으로 반복 원인과 자동화 가능 비율을 측정한다.",
            "pass_condition": "반복 원인 상위 유형이 전체 문의의 30% 이상이며 고객 3곳 이상이 파일럿 의향을 보인다.",
            "fail_condition": "반복 원인이 10% 미만이거나 파일럿 의향 고객이 없다.",
        },
        "evidence_refs": ["claim-market-1", "claim-market-2", "claim-risk-1"],
    }
    state["detailed_analysis"] = {
        key: {
            "summary": f"{key}에 대한 검증 가능한 분석 요약",
            "evidence_refs": ["claim-market-1"] if key != "evidence_against" else ["claim-risk-1"],
        }
        for key in DETAIL_SECTION_KEYS
    }
    return state


class EvolutionStateTests(unittest.TestCase):
    def test_raw_idea_is_preserved_verbatim(self):
        idea = "  고객 문의를 AI가 분류하고 답변 초안을 만드는 시스템  "
        state = create_evolution_state(idea, "evo_test0001")
        self.assertEqual(state["raw_idea"], idea)

    def test_new_state_has_explicit_empty_decision_slots(self):
        state = create_evolution_state(
            "고객 문의를 자동 분류하고 처리하는 시스템",
            "evo_test0002",
        )
        self.assertEqual(state["report_status"], "draft")
        self.assertIsNone(state["decision"])
        self.assertIsNone(state["human_decision"])
        self.assertEqual(state["evidence_refs"], [])

    def test_state_has_stable_required_keys(self):
        state = create_evolution_state(
            "업로드 문서를 읽고 핵심 데이터를 추출하는 자동화 시스템",
            "evo_test0003",
        )
        self.assertEqual(
            set(state),
            {
                "evolution_id",
                "raw_idea",
                "normalized_intent",
                "evolved_idea",
                "report_status",
                "decision",
                "confidence",
                "human_decision",
                "selected_concept_id",
                "executive_brief",
                "detailed_analysis",
                "evidence_refs",
            },
        )

    def test_invalid_evolution_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "evolution_id"):
            create_evolution_state("문서 입력을 자동 처리하는 업무 시스템", "bad-id")

    def test_invalid_decision_vocabulary_is_rejected(self):
        state = create_evolution_state("문서 입력을 자동 처리하는 업무 시스템", "evo_test0004")
        state["decision"] = "MAYBE"
        with self.assertRaisesRegex(ValueError, "decision"):
            validate_evolution_state(state)

    def test_non_string_or_empty_idea_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "raw_idea"):
            create_evolution_state("   ", "evo_test0005")
        with self.assertRaisesRegex(ValueError, "raw_idea"):
            create_evolution_state(123, "evo_test0006")


class ExecutiveReportContractTests(unittest.TestCase):
    def test_complete_report_fixture_is_valid(self):
        validate_complete_report(make_complete_state())

    def test_executive_brief_rejects_missing_required_field(self):
        brief = make_complete_state()["executive_brief"]
        brief.pop("why_now")
        with self.assertRaisesRegex(ValueError, "executive_brief"):
            validate_executive_brief(brief)

    def test_reasons_for_and_against_require_exactly_three_items(self):
        brief = make_complete_state()["executive_brief"]
        brief["reasons_against"] = ["하나", "둘"]
        with self.assertRaisesRegex(ValueError, "reasons_against"):
            validate_executive_brief(brief)

    def test_critical_unknowns_cannot_be_empty(self):
        brief = make_complete_state()["executive_brief"]
        brief["critical_unknowns"] = []
        with self.assertRaisesRegex(ValueError, "critical_unknowns"):
            validate_executive_brief(brief)

    def test_detailed_analysis_requires_every_canonical_section(self):
        details = make_complete_state()["detailed_analysis"]
        details.pop("evidence_against")
        with self.assertRaisesRegex(ValueError, "detailed_analysis"):
            validate_detailed_analysis(details)

    def test_report_rejects_unregistered_evidence_reference(self):
        state = make_complete_state()
        state["executive_brief"]["evidence_refs"].append("claim-unknown")
        with self.assertRaisesRegex(ValueError, "evidence"):
            validate_complete_report(state)


if __name__ == "__main__":
    unittest.main()
