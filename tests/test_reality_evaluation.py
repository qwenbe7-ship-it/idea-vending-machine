import unittest

from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.reality_evaluation import derive_reality_assessment


def candidate():
    return {
        "candidate_id": "candidate_123456789abc",
        "family": "adjacent_innovation",
        "name": "Evidence-aware workflow",
        "one_sentence_concept": "Turn late manual review into a verified preventive workflow.",
    }


def critique(*, status="strong", unknown=None, blocker=None):
    dimensions = []
    for dimension in sorted(EVALUATION_DIMENSIONS):
        item = {
            "dimension": dimension,
            "status": status,
            "rationale": f"Rationale for {dimension}",
            "supporting_claim_ids": ["claim_support01"],
            "contradicting_claim_ids": [],
            "material_unknowns": [],
            "blockers": [],
        }
        dimensions.append(item)
    if unknown:
        dimensions[0]["status"] = "unknown"
        dimensions[0]["material_unknowns"] = [unknown]
    if blocker:
        dimensions[0]["blockers"] = [blocker]
    return {
        "target_type": "candidate",
        "target_id": "candidate_123456789abc",
        "dimensions": dimensions,
        "strongest_reason_for": "Buyer value is evidence-backed.",
        "strongest_reason_against": "Distribution still requires proof.",
        "unacceptable_conditions": ["No measurable buyer value"],
        "cheapest_next_validation": "Run five buyer interviews.",
        "recommendation": "advance",
    }


def gate(classification, *, hold_reasons=None, decisive=None):
    return {
        "classification": classification,
        "hold_reasons": hold_reasons or [],
        "decisive_failure_reasons": decisive or [],
        "material_unknowns": [],
        "material_collision_count": 0,
        "feasibility_level": "T4",
    }


class RealityEvaluationTests(unittest.TestCase):
    def test_material_unknown_is_hold_never_reject(self):
        result = derive_reality_assessment(
            candidate=candidate(),
            critique=critique(unknown="Need direct buyer evidence"),
            gate_result=gate("hold", hold_reasons=["material_unknowns"]),
            confidence="low",
        )
        self.assertEqual(result["reality_verdict"], "HOLD")

    def test_unresolvable_evidence_backed_hard_blocker_is_reject(self):
        result = derive_reality_assessment(
            candidate=candidate(),
            critique=critique(
                blocker={
                    "reason": "Fatal regulatory prohibition",
                    "materiality": "hard",
                    "evidence_claim_ids": ["claim_blocker01"],
                    "resolvable": False,
                }
            ),
            gate_result=gate(
                "eliminated", decisive=["Fatal regulatory prohibition"]
            ),
            confidence="high",
        )
        self.assertEqual(result["reality_verdict"], "REJECT")

    def test_resolvable_material_blocker_is_revise(self):
        result = derive_reality_assessment(
            candidate=candidate(),
            critique=critique(
                status="mixed",
                blocker={
                    "reason": "Distribution design must change",
                    "materiality": "material",
                    "evidence_claim_ids": ["claim_blocker01"],
                    "resolvable": True,
                },
            ),
            gate_result=gate("hold", hold_reasons=["resolvable_blocker"]),
            confidence="medium",
        )
        self.assertEqual(result["reality_verdict"], "REVISE")

    def test_strong_eligible_candidate_advances(self):
        result = derive_reality_assessment(
            candidate=candidate(),
            critique=critique(),
            gate_result=gate("eligible"),
            confidence="high",
        )
        self.assertEqual(result["reality_verdict"], "ADVANCE")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(set(result["dimension_statuses"]), EVALUATION_DIMENSIONS)

    def test_provider_recommendation_does_not_control_reality_verdict(self):
        item = critique()
        item["recommendation"] = "reject"
        result = derive_reality_assessment(
            candidate=candidate(),
            critique=item,
            gate_result=gate("eligible"),
            confidence="high",
        )
        self.assertEqual(result["reality_verdict"], "ADVANCE")


if __name__ == "__main__":
    unittest.main()
