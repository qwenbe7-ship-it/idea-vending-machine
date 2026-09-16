from copy import deepcopy
import unittest

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evolution_runtime import run_evolution
from tests.test_evolution_runtime import (
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
)


class RecordingIdeationProvider(FakeIdeationProvider):
    def __init__(self):
        super().__init__()
        self.requests = []

    def generate(self, request):
        self.requests.append(deepcopy(request))
        return super().generate(request)


class E2ARuntimeContractTests(unittest.TestCase):
    def test_completed_response_exposes_baseline_plus_ten_critiques(self):
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(result["runtime"]["status"], "completed")
        self.assertEqual(len(result["critiques"]), 11)
        self.assertEqual(
            sum(1 for item in result["critiques"] if item["target_type"] == "baseline"),
            1,
        )
        candidate_critiques = [
            item for item in result["critiques"] if item["target_type"] == "candidate"
        ]
        self.assertEqual(len(candidate_critiques), 10)
        self.assertEqual(
            {item["target_id"] for item in candidate_critiques},
            {item["candidate_id"] for item in result["candidates"]},
        )
        self.assertEqual(
            result["state"]["candidate_reality_assessments"],
            result["candidate_reality_assessments"],
        )

    def test_forge_provider_request_requires_all_ten_canonical_families(self):
        ideation = RecordingIdeationProvider()
        result = run_evolution(
            "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템",
            research_provider=FakeResearchProvider(),
            ideation_provider=ideation,
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(result["runtime"]["status"], "completed")
        forge = next(
            request for request in ideation.requests if request["operation"] == "forge_candidates"
        )
        self.assertIn("exactly ten", forge["objective"].lower())
        self.assertNotIn("four canonical", forge["objective"].lower())
        family_schema = forge["required_output_schema"]["properties"]["candidates"]["items"]["properties"]["family"]
        self.assertEqual(set(family_schema["enum"]), CANDIDATE_FAMILIES)
        constraint_text = " ".join(forge["constraints"]).lower()
        self.assertIn("exactly ten", constraint_text)
        for family in CANDIDATE_FAMILIES:
            self.assertIn(family, constraint_text)


if __name__ == "__main__":
    unittest.main()
