import copy
import unittest

from src.idea_vending.evidence_attachment import (
    attach_evidence_refs,
    validate_state_evidence_against_graph,
)
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)
from src.idea_vending.evolution_schema import DETAIL_SECTION_KEYS, create_evolution_state
from tests.test_evolution_schema import make_reality_assessments


class EvidenceAttachmentTests(unittest.TestCase):
    def make_graph(self):
        graph = create_evidence_graph("evo_attach001")
        for index, direction in ((1, "supports"), (2, "contradicts")):
            add_evidence_record(
                graph,
                create_evidence_record(
                    evidence_id=f"ev_attach00{index}",
                    claim_id=f"claim_attach00{index}",
                    claim=f"Decision claim {index}",
                    source_title=f"Source {index}",
                    source_url=f"https://example.com/source-{index}",
                    publisher="Publisher",
                    publication_date="2026-08-01",
                    retrieved_at="2026-09-16",
                    geography="Global",
                    population_or_market_definition="Target market",
                    evidence_type="primary_source",
                    supports_or_contradicts=direction,
                    confidence_tier="A" if index == 1 else "B",
                    freshness_status="current",
                    candidate_ids=[],
                    notes="",
                    raw_content_untrusted="untrusted excerpt",
                    provider_metadata={"provider": "fixture"},
                    market_size=None,
                ),
            )
        return graph

    def make_state(self):
        state = create_evolution_state(
            "  업로드 문서를 분석해 기업 의사결정을 돕는 시스템  ",
            "evo_attach001",
        )
        state["normalized_intent"] = "기업 의사결정 품질 개선"
        state["decision"] = "MODIFY"
        state["confidence"] = "medium"
        state["evolved_idea"] = "근거 기반 의사결정 엔진"
        return state

    def make_complete_state(self):
        state = self.make_state()
        state["report_status"] = "complete"
        state["evidence_refs"] = ["claim_attach001"]
        assessments = make_reality_assessments()
        for assessment in assessments:
            assessment["evidence_claim_ids"] = ["claim_attach001"]
        state["candidate_reality_assessments"] = assessments
        state["executive_brief"] = {
            "thesis": "검증된 근거가 있을 때만 투자 판단을 진행한다.",
            "why_now": "AI 도입 확산과 의사결정 품질 격차가 동시에 커지고 있다.",
            "evolution_delta": "단순 분석 도구에서 투자판단 엔진으로 전환한다.",
            "market_snapshot": {
                "stage": "category formation",
                "current_market": [],
                "forecast_market": [],
                "growth": [],
                "buyer": "기업 대표와 신규사업 책임자",
            },
            "best_customer": "실제 자본배분 결정을 앞둔 기업",
            "business_value": "잘못된 투자와 개발비를 줄인다.",
            "reasons_for": ["문제가 크다", "구매자가 명확하다", "검증 가능하다"],
            "reasons_against": ["신뢰 구축이 어렵다", "범용 AI 경쟁", "데이터 품질 위험"],
            "critical_unknowns": ["실제 지불의사"],
            "cheapest_next_validation": {
                "action": "대표 5명에게 보고서 기반 의사결정 테스트",
                "pass_condition": "3명 이상이 유료 재사용 의사 표시",
                "fail_condition": "2명 이하만 유료 재사용 의사 표시",
            },
            "evidence_refs": ["claim_attach001"],
        }
        state["detailed_analysis"] = {
            key: {
                "summary": f"{key}에 대한 검증 가능한 분석 요약",
                "evidence_refs": ["claim_attach001"] if key == "evidence_for" else [],
            }
            for key in DETAIL_SECTION_KEYS
        }
        return state

    def test_attach_known_claim_ids_to_state(self):
        graph = self.make_graph()
        state = self.make_state()
        original_raw = state["raw_idea"]
        original_decision = state["decision"]

        attach_evidence_refs(state, graph, ["claim_attach001", "claim_attach002"])

        self.assertEqual(
            state["evidence_refs"],
            ["claim_attach001", "claim_attach002"],
        )
        self.assertEqual(state["raw_idea"], original_raw)
        self.assertEqual(state["decision"], original_decision)

    def test_attach_rejects_unknown_claim_id(self):
        with self.assertRaisesRegex(ValueError, "unknown claim_id"):
            attach_evidence_refs(
                self.make_state(),
                self.make_graph(),
                ["claim_missing001"],
            )

    def test_attach_rejects_duplicate_new_refs(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            attach_evidence_refs(
                self.make_state(),
                self.make_graph(),
                ["claim_attach001", "claim_attach001"],
            )

    def test_attach_rejects_ref_already_registered(self):
        state = self.make_state()
        state["evidence_refs"] = ["claim_attach001"]
        with self.assertRaisesRegex(ValueError, "already registered"):
            attach_evidence_refs(state, self.make_graph(), ["claim_attach001"])

    def test_graph_and_state_must_share_evolution_id(self):
        state = self.make_state()
        state["evolution_id"] = "evo_different01"
        with self.assertRaisesRegex(ValueError, "evolution_id"):
            validate_state_evidence_against_graph(state, self.make_graph())

    def test_complete_report_cannot_reference_claim_absent_from_graph(self):
        state = self.make_complete_state()
        state["evidence_refs"] = ["claim_attach001", "claim_missing001"]
        with self.assertRaisesRegex(ValueError, "absent from Evidence Graph"):
            validate_state_evidence_against_graph(state, self.make_graph())

    def test_valid_complete_report_is_traceable_to_graph(self):
        state = self.make_complete_state()
        snapshot = copy.deepcopy(state)
        validate_state_evidence_against_graph(state, self.make_graph())
        self.assertEqual(state, snapshot)


if __name__ == "__main__":
    unittest.main()
