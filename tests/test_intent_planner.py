from copy import deepcopy
import unittest

from src.idea_vending.intent_planner import (
    RESEARCH_PLAN_CATEGORIES,
    build_intent_request,
    build_research_plan_request,
    research_plan_schema,
    validate_research_plan,
)
from tests.test_intent_model import VALID_INTENT


VALID_PLAN = {
    "research_questions": {
        "market_customer_demand": ["이 문제를 실제로 반복해서 겪는 구매자는 누구이며 수요가 얼마나 강한가?"],
        "workflow_economics": ["현재 반복 문의 처리에 시간과 비용이 얼마나 들어가는가?"],
        "alternatives_incumbents": ["현재 고객은 어떤 대안과 기존 도구로 문제를 해결하는가?"],
        "implementation_feasibility": ["문의 분류와 근거 검색을 안정적으로 자동화할 수 있는가?"],
        "data_quality": ["필요한 문의·지식 데이터에 접근 가능하고 품질은 충분한가?"],
        "regulation_security": ["고객 데이터 처리에 적용되는 보안·개인정보 제약은 무엇인가?"],
        "failure_blockers": ["오답·권한·채택 실패를 일으키는 결정적 blocker는 무엇인가?"],
        "adjacent_mechanisms": ["다른 산업에서 반복 대응을 예방한 메커니즘을 이전할 수 있는가?"],
    }
}


class IntentPlannerTests(unittest.TestCase):
    def test_intent_request_is_provider_neutral_and_forbids_fabrication(self):
        request = build_intent_request("고객 문의 반복업무를 자동화하고 싶다")

        self.assertEqual(request["operation"], "interpret_intent")
        self.assertEqual(request["raw_idea"], "고객 문의 반복업무를 자동화하고 싶다")
        self.assertEqual(request["required_output_schema"]["properties"]["material_unknowns"]["type"], "array")
        constraints = " ".join(request["constraints"]).lower()
        self.assertIn("unknown", constraints)
        self.assertIn("invent", constraints)
        self.assertEqual(request["evidence_summary"], [])

    def test_research_plan_schema_requires_exactly_all_bounded_categories(self):
        schema = research_plan_schema()
        questions = schema["properties"]["research_questions"]

        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(questions["additionalProperties"])
        self.assertEqual(set(questions["required"]), set(RESEARCH_PLAN_CATEGORIES))
        self.assertEqual(set(questions["properties"]), set(RESEARCH_PLAN_CATEGORIES))
        for category in RESEARCH_PLAN_CATEGORIES:
            self.assertEqual(questions["properties"][category]["type"], "array")
            self.assertEqual(questions["properties"][category]["minItems"], 1)

    def test_research_plan_request_preserves_constraints_metrics_and_unknowns(self):
        intent = deepcopy(VALID_INTENT)
        intent["hard_constraints"] = ["사람 승인 없이 환불을 실행하지 않는다."]
        intent["success_metrics"] = ["수작업 처리시간 50% 감소"]
        intent["material_unknowns"] = ["실제 구매자의 지불의사"]

        request = build_research_plan_request(intent)
        context = request["problem_context"]["intent_model"]

        self.assertEqual(request["operation"], "plan_research")
        self.assertEqual(context["hard_constraints"], intent["hard_constraints"])
        self.assertEqual(context["success_metrics"], intent["success_metrics"])
        self.assertEqual(context["material_unknowns"], intent["material_unknowns"])
        self.assertEqual(request["required_output_schema"], research_plan_schema())
        constraints = " ".join(request["constraints"]).lower()
        self.assertIn("evidence", constraints)
        self.assertIn("question", constraints)

    def test_research_plan_validator_rejects_missing_category_and_evidence_payload(self):
        self.assertEqual(validate_research_plan(deepcopy(VALID_PLAN)), VALID_PLAN)

        missing = deepcopy(VALID_PLAN)
        missing["research_questions"].pop("data_quality")
        with self.assertRaisesRegex(ValueError, "research plan categories"):
            validate_research_plan(missing)

        evidence = {**deepcopy(VALID_PLAN), "evidence": [{"claim": "not allowed"}]}
        with self.assertRaisesRegex(ValueError, "research plan keys"):
            validate_research_plan(evidence)


if __name__ == "__main__":
    unittest.main()
