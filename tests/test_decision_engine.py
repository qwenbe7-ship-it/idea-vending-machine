import unittest

from src.idea_vending.decision_engine import (
    ANCHOR_DIMENSIONS,
    classify_option,
    compare_evolution_delta,
    derive_confidence,
)
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS


class DeterministicHardGateTests(unittest.TestCase):
    def critique(self, *, status="strong", unknown_dimension=None, blocker=None):
        dimensions = []
        for name in sorted(EVALUATION_DIMENSIONS):
            dimensions.append(
                {
                    "dimension": name,
                    "status": "unknown" if name == unknown_dimension else status,
                    "rationale": f"Assessment of {name}",
                    "supporting_claim_ids": ["claim_a"],
                    "contradicting_claim_ids": ["claim_b"],
                    "material_unknowns": ["material fact unresolved"] if name == unknown_dimension else [],
                    "blockers": [blocker] if blocker and name == "technical_feasibility" else [],
                }
            )
        return {
            "target_type": "candidate",
            "target_id": "candidate_123456789abc",
            "dimensions": dimensions,
            "strongest_reason_for": "Strong buyer value",
            "strongest_reason_against": "Competitive pressure",
            "unacceptable_conditions": ["Buyer economics fail"],
            "cheapest_next_validation": "Buyer interviews",
            "recommendation": "advance",
        }

    def evidence_audit(self, **overrides):
        data = {
            "decision_ready": True,
            "counter_evidence_complete": True,
            "freshness_ready": True,
            "tier_ab_support_ready": True,
            "noncritical_secondary_only": False,
        }
        data.update(overrides)
        return data

    def feasibility(self, level="T4", **overrides):
        data = {
            "level": level,
            "blocking_dependency_resolved": False,
            "resolution_path_exists": True,
        }
        data.update(overrides)
        return data

    def test_material_unknown_forces_hold(self):
        result = classify_option(
            self.critique(unknown_dimension="buyer_economics"),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility(),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "hold")
        self.assertIn("material_unknowns", result["hold_reasons"])

    def test_unresolved_material_collision_forces_hold(self):
        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[{"materiality": "material", "question": "Is prior art blocking?"}],
            feasibility_artifact=self.feasibility(),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "hold")
        self.assertIn("material_collision", result["hold_reasons"])

    def test_evidence_backed_hard_blocker_eliminates_but_resolvable_holds(self):
        hard = {
            "reason": "Required data cannot legally be obtained",
            "materiality": "hard",
            "evidence_claim_ids": ["claim_b"],
            "resolvable": False,
        }
        result = classify_option(
            self.critique(blocker=hard),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility(),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "eliminated")
        self.assertTrue(result["decisive_failure_reasons"])

        hard["resolvable"] = True
        result = classify_option(
            self.critique(blocker=hard),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility(),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "hold")

    def test_t3_to_t5_can_be_eligible_and_t2_normally_holds(self):
        for level in ("T3", "T4", "T5"):
            result = classify_option(
                self.critique(),
                unresolved_collision_requests=[],
                feasibility_artifact=self.feasibility(level),
                evidence_audit=self.evidence_audit(),
            )
            self.assertEqual(result["classification"], "eligible")

        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility("T2"),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "hold")

        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility("T2", blocking_dependency_resolved=True),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "eligible")

    def test_t1_never_becomes_eligible(self):
        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility("T1", resolution_path_exists=True),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "hold")
        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility("T1", resolution_path_exists=False),
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(result["classification"], "eliminated")

    def test_missing_decision_evidence_holds_instead_of_eliminating(self):
        result = classify_option(
            self.critique(),
            unresolved_collision_requests=[],
            feasibility_artifact=self.feasibility(),
            evidence_audit=self.evidence_audit(decision_ready=False),
        )
        self.assertEqual(result["classification"], "hold")
        self.assertFalse(result["decisive_failure_reasons"])

    def test_confidence_is_deterministic_and_positive_low_is_not_allowed(self):
        critique = self.critique()
        high = derive_confidence(
            critique,
            classification="eligible",
            unresolved_collision_requests=[],
            evidence_audit=self.evidence_audit(),
        )
        self.assertEqual(high, "high")
        medium = derive_confidence(
            critique,
            classification="eligible",
            unresolved_collision_requests=[],
            evidence_audit=self.evidence_audit(
                tier_ab_support_ready=True,
                noncritical_secondary_only=True,
            ),
        )
        self.assertEqual(medium, "medium")
        low = derive_confidence(
            self.critique(unknown_dimension="buyer_economics"),
            classification="hold",
            unresolved_collision_requests=[],
            evidence_audit=self.evidence_audit(decision_ready=False),
        )
        self.assertEqual(low, "low")

    def test_evolution_delta_uses_rule_based_dimension_comparison(self):
        self.assertEqual(
            ANCHOR_DIMENSIONS,
            {"problem_evidence", "buyer_economics", "structural_differentiation", "technical_feasibility"},
        )
        baseline = self.critique(status="mixed")
        candidate = self.critique(status="mixed")
        for item in candidate["dimensions"]:
            if item["dimension"] in {"buyer_economics", "structural_differentiation"}:
                item["status"] = "strong"
        delta = compare_evolution_delta(baseline, candidate)
        self.assertTrue(delta["material_improvement"])
        self.assertEqual(len(delta["better_dimensions"]), 2)

        for item in candidate["dimensions"]:
            if item["dimension"] == "technical_feasibility":
                item["status"] = "unknown"
        delta = compare_evolution_delta(baseline, candidate)
        self.assertFalse(delta["comparable"])


if __name__ == "__main__":
    unittest.main()
