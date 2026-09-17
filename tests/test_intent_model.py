from copy import deepcopy
import unittest

from src.idea_vending.intent_model import (
    INTENT_MODEL_KEYS,
    intent_model_schema,
    validate_intent_model,
)


VALID_INTENT = {
    "primary_objective": "반복적인 고객 문의 대응을 자동화해 운영 시간을 줄인다.",
    "desired_outcome": "고객 응답 품질을 유지하면서 수작업 처리량을 줄인다.",
    "primary_buyer": "중소 전자상거래 운영팀",
    "primary_user": "고객지원 담당자",
    "jobs_to_be_done": ["반복 문의를 빠르게 분류하고 일관된 답변을 제공한다."],
    "hard_constraints": ["사람 승인 없이 환불을 실행하지 않는다."],
    "soft_preferences": ["기존 운영 도구를 최대한 유지한다."],
    "success_metrics": ["반복 문의 수작업 처리시간 50% 감소"],
    "non_goals": ["결제나 환불을 자율 실행하지 않는다."],
    "risk_tolerance": "낮음 — 고객에게 잘못된 답변을 보내는 위험을 최소화한다.",
    "automation_target": "문의 분류, 근거 검색, 답변 초안 생성",
    "evidence_questions": ["반복 문의가 전체 고객지원 처리시간에서 차지하는 비율은 얼마인가?"],
    "material_unknowns": ["실제 문의 채널별 데이터 접근 권한"],
    "interpretation_notes": ["자동화는 초안 생성까지이며 외부 실행은 범위 밖으로 해석했다."],
}


class IntentModelContractTests(unittest.TestCase):
    def test_schema_is_exact_and_exposes_unknown_safe_fields(self):
        schema = intent_model_schema()
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), INTENT_MODEL_KEYS)
        self.assertEqual(set(schema["properties"]), INTENT_MODEL_KEYS)

        self.assertEqual(schema["properties"]["hard_constraints"]["type"], "array")
        self.assertEqual(schema["properties"]["success_metrics"]["type"], "array")
        self.assertEqual(schema["properties"]["material_unknowns"]["type"], "array")
        self.assertIn("null", schema["properties"]["primary_buyer"]["type"])
        self.assertIn("null", schema["properties"]["primary_user"]["type"])
        self.assertIn("null", schema["properties"]["risk_tolerance"]["type"])
        self.assertIn("null", schema["properties"]["automation_target"]["type"])

    def test_valid_model_is_normalized_and_defensively_copied(self):
        raw = deepcopy(VALID_INTENT)
        raw["primary_objective"] = "  " + raw["primary_objective"] + "  "
        raw["hard_constraints"] = ["  " + raw["hard_constraints"][0] + "  "]

        intent = validate_intent_model(raw)

        self.assertEqual(set(intent), INTENT_MODEL_KEYS)
        self.assertEqual(intent["primary_objective"], VALID_INTENT["primary_objective"])
        self.assertEqual(intent["hard_constraints"], VALID_INTENT["hard_constraints"])
        raw["hard_constraints"][0] = "mutated"
        self.assertEqual(intent["hard_constraints"], VALID_INTENT["hard_constraints"])

    def test_unknown_buyer_and_success_metric_remain_explicit_unknowns(self):
        raw = deepcopy(VALID_INTENT)
        raw["primary_buyer"] = None
        raw["primary_user"] = None
        raw["success_metrics"] = []
        raw["risk_tolerance"] = None
        raw["automation_target"] = None
        raw["material_unknowns"] = [
            "primary_buyer",
            "primary_user",
            "success_metrics",
            "risk_tolerance",
            "automation_target",
        ]

        intent = validate_intent_model(raw)

        self.assertIsNone(intent["primary_buyer"])
        self.assertIsNone(intent["primary_user"])
        self.assertEqual(intent["success_metrics"], [])
        self.assertIsNone(intent["risk_tolerance"])
        self.assertIsNone(intent["automation_target"])
        self.assertEqual(intent["material_unknowns"], raw["material_unknowns"])

    def test_contradictory_constraints_remain_visible_instead_of_being_reconciled(self):
        raw = deepcopy(VALID_INTENT)
        raw["hard_constraints"] = [
            "모든 고객 응답은 사람 승인을 거쳐야 한다.",
            "모든 고객 응답은 사람 승인 없이 즉시 전송되어야 한다.",
        ]
        raw["material_unknowns"] = [
            "상충하는 승인 요구사항 중 어떤 것이 실제 운영 우선순위인지 확인 필요"
        ]

        intent = validate_intent_model(raw)

        self.assertEqual(intent["hard_constraints"], raw["hard_constraints"])
        self.assertEqual(intent["material_unknowns"], raw["material_unknowns"])

    def test_rejects_extra_keys_blank_material_text_and_invalid_lists(self):
        extra = {**VALID_INTENT, "invented_fact": "should not exist"}
        with self.assertRaisesRegex(ValueError, "intent model keys"):
            validate_intent_model(extra)

        blank = {**VALID_INTENT, "desired_outcome": "   "}
        with self.assertRaisesRegex(ValueError, "desired_outcome"):
            validate_intent_model(blank)

        duplicate = {**VALID_INTENT, "hard_constraints": ["same", "same"]}
        with self.assertRaisesRegex(ValueError, "hard_constraints"):
            validate_intent_model(duplicate)

        invalid = {**VALID_INTENT, "jobs_to_be_done": ["valid", 3]}
        with self.assertRaisesRegex(ValueError, "jobs_to_be_done"):
            validate_intent_model(invalid)


if __name__ == "__main__":
    unittest.main()
