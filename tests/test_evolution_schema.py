import unittest

from src.idea_vending.evolution_schema import create_evolution_state, validate_evolution_state


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
            create_evolution_state(
                "문서 입력을 자동 처리하는 업무 시스템",
                "bad-id",
            )

    def test_invalid_decision_vocabulary_is_rejected(self):
        state = create_evolution_state(
            "문서 입력을 자동 처리하는 업무 시스템",
            "evo_test0004",
        )
        state["decision"] = "MAYBE"
        with self.assertRaisesRegex(ValueError, "decision"):
            validate_evolution_state(state)

    def test_non_string_or_empty_idea_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "raw_idea"):
            create_evolution_state("   ", "evo_test0005")
        with self.assertRaisesRegex(ValueError, "raw_idea"):
            create_evolution_state(123, "evo_test0006")


if __name__ == "__main__":
    unittest.main()
