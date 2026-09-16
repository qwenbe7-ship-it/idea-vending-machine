import unittest

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evolution_runtime import (
    finalize_evolution_from_forge,
    run_evolution,
    run_forge_phase,
)
from tests.test_evolution_runtime import (
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
)


IDEA = "고객 반복업무를 예방적으로 자동화하고 운영 데이터를 의사결정 자산으로 만드는 시스템"


class RuntimePhaseSplitTests(unittest.TestCase):
    def test_forge_phase_stops_before_independent_evaluation(self):
        forge = run_forge_phase(
            IDEA,
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            now_provider=lambda: NOW,
        )
        self.assertEqual(
            set(forge),
            {
                "analysis",
                "state",
                "evidence_graph",
                "runtime",
                "baseline",
                "assumptions",
                "challenges",
                "transformations",
                "mechanisms",
                "candidates",
                "feasibility_artifacts",
                "collision_state",
            },
        )
        self.assertEqual(
            {candidate["family"] for candidate in forge["candidates"]},
            CANDIDATE_FAMILIES,
        )
        self.assertIsNone(forge["state"]["decision"])
        self.assertEqual(forge["state"]["report_status"], "pending")
        operations = [run["operation"] for run in forge["runtime"]["provider_runs"]]
        self.assertNotIn("independent_evaluation", operations)

    def test_split_path_preserves_one_shot_business_result(self):
        one_shot = run_evolution(
            IDEA,
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        forge = run_forge_phase(
            IDEA,
            research_provider=FakeResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            now_provider=lambda: NOW,
        )
        split = finalize_evolution_from_forge(
            forge,
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )
        self.assertEqual(split["runtime"]["status"], "completed")
        self.assertEqual(split["state"]["decision"], one_shot["state"]["decision"])
        self.assertEqual(split["state"]["confidence"], one_shot["state"]["confidence"])
        self.assertEqual(split["candidates"], one_shot["candidates"])
        self.assertEqual(split["evidence_graph"], one_shot["evidence_graph"])
        self.assertEqual(
            split["candidate_reality_assessments"],
            one_shot["candidate_reality_assessments"],
        )


if __name__ == "__main__":
    unittest.main()
