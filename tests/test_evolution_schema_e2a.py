import copy
import unittest

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.evolution_schema import create_evolution_state, validate_complete_report
from tests.test_evolution_schema import make_complete_state


FAMILIES = sorted(CANDIDATE_FAMILIES)


def make_assessments():
    records = []
    for index, family in enumerate(FAMILIES):
        records.append(
            {
                "candidate_id": f"candidate_{index:012x}",
                "family": family,
                "name": f"Reality candidate {index}",
                "one_sentence_concept": f"Evidence-aware evolved concept {index}",
                "reality_verdict": "ADVANCE" if index == 0 else "HOLD",
                "confidence": "medium",
                "strongest_reason_for": f"Evidence-backed value reason {index}",
                "strongest_reason_against": f"Evidence-backed risk reason {index}",
                "dimension_statuses": {
                    dimension: ("strong" if index == 0 else "mixed")
                    for dimension in EVALUATION_DIMENSIONS
                },
                "hard_or_material_blockers": [],
                "material_unknowns": [] if index == 0 else [f"Unknown {index}"],
                "cheapest_next_validation": f"Run validation {index}",
                "evidence_claim_ids": ["claim-market-1"],
            }
        )
    return records


class E2ACompleteReportContractTests(unittest.TestCase):
    def test_new_state_has_explicit_reality_assessment_slot(self):
        state = create_evolution_state("고객 운영을 자동화하는 아이디어", "evo_e2a00001")
        self.assertEqual(state["candidate_reality_assessments"], [])

    def test_complete_report_requires_exactly_ten_unique_reality_assessments(self):
        state = make_complete_state()
        state["candidate_reality_assessments"] = make_assessments()
        validate_complete_report(state)
        self.assertEqual(len(state["candidate_reality_assessments"]), 10)
        self.assertEqual(
            {item["family"] for item in state["candidate_reality_assessments"]},
            CANDIDATE_FAMILIES,
        )

    def test_duplicate_reality_candidate_id_is_rejected(self):
        state = make_complete_state()
        assessments = make_assessments()
        assessments[-1] = copy.deepcopy(assessments[-1])
        assessments[-1]["candidate_id"] = assessments[0]["candidate_id"]
        state["candidate_reality_assessments"] = assessments
        with self.assertRaisesRegex(ValueError, "candidate"):
            validate_complete_report(state)


if __name__ == "__main__":
    unittest.main()
