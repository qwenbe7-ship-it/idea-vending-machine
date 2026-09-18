from copy import deepcopy
import unittest

from src.idea_vending.evolution_runtime import run_evolution
from src.idea_vending.provider_transport import ProviderTimeout
from tests.test_evolution_runtime import (
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
)
from tests.test_intent_model import VALID_INTENT
from tests.test_intent_planner import VALID_PLAN


class IntentRuntimeIdeationProvider(FakeIdeationProvider):
    supports_intent_planning = True

    def __init__(self):
        super().__init__()
        self.requests = []

    def generate(self, request):
        self.requests.append(deepcopy(request))
        operation = request["operation"]
        if operation == "interpret_intent":
            self.calls.append(operation)
            self._mark(operation)
            return deepcopy(VALID_INTENT)
        if operation == "plan_research":
            self.calls.append(operation)
            self._mark(operation)
            return deepcopy(VALID_PLAN)
        return super().generate(request)


class TimeoutIntentIdeationProvider(FakeIdeationProvider):
    supports_intent_planning = True

    def generate(self, request):
        if request["operation"] == "interpret_intent":
            raise ProviderTimeout("provider request timed out")
        return super().generate(request)


class CapturingResearchProvider(FakeResearchProvider):
    def __init__(self):
        super().__init__()
        self.requests = []

    def research(self, request):
        self.requests.append(deepcopy(request))
        return super().research(request)


class IntentRuntimeIntegrationTests(unittest.TestCase):
    def test_intent_and_research_plan_run_before_landscape_and_drive_downstream_requests(self):
        ideation = IntentRuntimeIdeationProvider()
        research = CapturingResearchProvider()
        result = run_evolution(
            "고객 문의 반복업무를 자동화해 운영 시간을 줄이고 싶다",
            research_provider=research,
            ideation_provider=ideation,
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )

        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertGreaterEqual(len(ideation.calls), 2)
        self.assertEqual(ideation.calls[:2], ["interpret_intent", "plan_research"])
        self.assertEqual(result["state"]["normalized_intent"], VALID_INTENT["primary_objective"])

        self.assertEqual([item["pass_type"] for item in research.requests], ["landscape", "collision"])
        landscape_text = " ".join(
            [research.requests[0]["question"], *research.requests[0]["queries"]]
        )
        self.assertIn(VALID_INTENT["hard_constraints"][0], landscape_text)
        self.assertIn(VALID_INTENT["success_metrics"][0], landscape_text)
        self.assertIn(VALID_INTENT["material_unknowns"][0], landscape_text)
        self.assertIn(
            VALID_PLAN["research_questions"]["market_customer_demand"][0],
            landscape_text,
        )

        downstream = [
            request
            for request in ideation.requests
            if request["operation"] in {
                "extract_assumptions",
                "challenge_assumptions",
                "propose_reframes",
                "discover_mechanisms",
                "forge_candidates",
            }
        ]
        self.assertEqual(len(downstream), 5)
        for request in downstream:
            context = request["problem_context"]
            self.assertEqual(context["intent_model"]["hard_constraints"], VALID_INTENT["hard_constraints"])
            self.assertEqual(context["intent_model"]["success_metrics"], VALID_INTENT["success_metrics"])
            self.assertEqual(context["intent_model"]["material_unknowns"], VALID_INTENT["material_unknowns"])
            self.assertEqual(context["research_plan"], VALID_PLAN)

    def test_research_plan_remains_question_only_in_runtime_context(self):
        ideation = IntentRuntimeIdeationProvider()
        research = CapturingResearchProvider()
        result = run_evolution(
            "고객 문의 반복업무를 자동화해 운영 시간을 줄이고 싶다",
            research_provider=research,
            ideation_provider=ideation,
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )

        self.assertEqual(result["runtime"]["status"], "completed")
        forge_request = next(
            request for request in ideation.requests if request["operation"] == "forge_candidates"
        )
        plan = forge_request["problem_context"]["research_plan"]
        self.assertEqual(set(plan), {"research_questions"})
        self.assertNotIn("evidence", plan)
        self.assertNotIn("sources", plan)

    def test_intent_provider_timeout_is_incomplete_without_business_verdict(self):
        result = run_evolution(
            "고객 문의 반복업무를 자동화해 운영 시간을 줄이고 싶다",
            research_provider=FakeResearchProvider(),
            ideation_provider=TimeoutIntentIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )

        self.assertEqual(result["runtime"]["status"], "incomplete")
        self.assertEqual(result["runtime"]["failure"]["code"], "provider_timeout")
        self.assertIsNone(result["state"]["decision"])
        self.assertIsNone(result["decision_result"])


if __name__ == "__main__":
    unittest.main()
