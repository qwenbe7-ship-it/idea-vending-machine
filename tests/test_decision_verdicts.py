import unittest

from src.idea_vending.decision_engine import decide_evolution, apply_decision_to_state
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS
from src.idea_vending.evolution_schema import create_evolution_state


class DecisionVerdictTests(unittest.TestCase):
    def critique(self, target_id, *, status="mixed", improvements=None):
        improvements = improvements or set()
        dimensions = []
        for name in sorted(EVALUATION_DIMENSIONS):
            dimensions.append(
                {
                    "dimension": name,
                    "status": "strong" if name in improvements else status,
                    "rationale": f"Assessment of {name}",
                    "supporting_claim_ids": ["claim_a"],
                    "contradicting_claim_ids": ["claim_b"],
                    "material_unknowns": [],
                    "blockers": [],
                }
            )
        return {
            "target_type": "baseline" if target_id.startswith("baseline_") else "candidate",
            "target_id": target_id,
            "dimensions": dimensions,
            "strongest_reason_for": "Reason for",
            "strongest_reason_against": "Reason against",
            "unacceptable_conditions": ["Critical economics fail"],
            "cheapest_next_validation": "Run targeted buyer validation",
            "recommendation": "advance",
        }

    def classification(self, value="eligible", decisive=None):
        return {
            "classification": value,
            "hold_reasons": [] if value != "hold" else ["evidence_not_ready"],
            "decisive_failure_reasons": decisive or [],
            "material_unknowns": [],
            "material_collision_count": 0,
            "feasibility_level": "T4",
        }

    def decide(self, baseline, candidates, *, baseline_class=None, candidate_classes=None, baseline_conf="high", candidate_confs=None):
        candidate_classes = candidate_classes or {
            item["target_id"]: self.classification() for item in candidates
        }
        candidate_confs = candidate_confs or {
            item["target_id"]: "high" for item in candidates
        }
        return decide_evolution(
            baseline_critique=baseline,
            candidate_critiques=candidates,
            baseline_classification=baseline_class or self.classification(),
            candidate_classifications=candidate_classes,
            baseline_confidence=baseline_conf,
            candidate_confidences=candidate_confs,
            comparison_validation_action="Run the smallest head-to-head buyer experiment.",
        )

    def test_eligible_baseline_without_materially_better_candidate_is_go(self):
        baseline = self.critique("baseline_123456789abc")
        candidate = self.critique("candidate_111111111111")
        result = self.decide(baseline, [candidate])
        self.assertEqual(result["decision"], "GO")
        self.assertIsNone(result["selected_concept_id"])
        self.assertEqual(result["confidence"], "high")

    def test_one_materially_better_candidate_is_modify(self):
        baseline = self.critique("baseline_123456789abc")
        candidate = self.critique(
            "candidate_111111111111",
            improvements={"buyer_economics", "structural_differentiation"},
        )
        result = self.decide(baseline, [candidate])
        self.assertEqual(result["decision"], "MODIFY")
        self.assertEqual(result["selected_concept_id"], candidate["target_id"])

    def test_multiple_qualifying_candidates_without_strict_dominance_hold(self):
        baseline = self.critique("baseline_123456789abc")
        left = self.critique(
            "candidate_111111111111",
            improvements={"buyer_economics", "structural_differentiation"},
        )
        right = self.critique(
            "candidate_222222222222",
            improvements={"problem_evidence", "technical_feasibility"},
        )
        result = self.decide(baseline, [left, right])
        self.assertEqual(result["decision"], "HOLD")
        self.assertIsNone(result["selected_concept_id"])
        self.assertIn("head-to-head", result["next_validation"])

    def test_strictly_dominant_candidate_can_be_modify(self):
        baseline = self.critique("baseline_123456789abc")
        dominant = self.critique(
            "candidate_111111111111",
            improvements={"problem_evidence", "buyer_economics", "structural_differentiation"},
        )
        other = self.critique(
            "candidate_222222222222",
            improvements={"buyer_economics", "structural_differentiation"},
        )
        result = self.decide(baseline, [dominant, other])
        self.assertEqual(result["decision"], "MODIFY")
        self.assertEqual(result["selected_concept_id"], dominant["target_id"])

    def test_low_confidence_material_candidate_forces_hold_not_false_go(self):
        baseline = self.critique("baseline_123456789abc")
        candidate = self.critique(
            "candidate_111111111111",
            improvements={"buyer_economics", "structural_differentiation"},
        )
        result = self.decide(
            baseline,
            [candidate],
            candidate_confs={candidate["target_id"]: "low"},
        )
        self.assertEqual(result["decision"], "HOLD")

    def test_missing_evidence_is_hold_never_kill(self):
        baseline = self.critique("baseline_123456789abc")
        candidate = self.critique("candidate_111111111111")
        result = self.decide(
            baseline,
            [candidate],
            baseline_class=self.classification("hold"),
            candidate_classes={candidate["target_id"]: self.classification("hold")},
            baseline_conf="low",
            candidate_confs={candidate["target_id"]: "low"},
        )
        self.assertEqual(result["decision"], "HOLD")

    def test_all_options_evidence_backed_eliminated_is_kill(self):
        baseline = self.critique("baseline_123456789abc")
        candidate = self.critique("candidate_111111111111")
        result = self.decide(
            baseline,
            [candidate],
            baseline_class=self.classification("eliminated", ["fatal baseline blocker"]),
            candidate_classes={
                candidate["target_id"]: self.classification("eliminated", ["fatal candidate blocker"])
            },
            baseline_conf="high",
            candidate_confs={candidate["target_id"]: "high"},
        )
        self.assertEqual(result["decision"], "KILL")
        self.assertTrue(result["decision_reasons"])

    def test_apply_modify_sets_string_evolved_idea_and_never_human_decision(self):
        state = create_evolution_state("Original idea", "evo_stateupd01")
        candidate = {
            "candidate_id": "candidate_111111111111",
            "one_sentence_concept": "Use preventive risk checks before commitment.",
        }
        result = {
            "decision": "MODIFY",
            "confidence": "high",
            "selected_concept_id": candidate["candidate_id"],
            "decision_reasons": ["Materially better candidate"],
            "next_validation": None,
        }
        updated = apply_decision_to_state(state, result, [candidate])
        self.assertEqual(updated["decision"], "MODIFY")
        self.assertEqual(updated["selected_concept_id"], candidate["candidate_id"])
        self.assertEqual(updated["evolved_idea"], candidate["one_sentence_concept"])
        self.assertIsNone(updated["human_decision"])

    def test_apply_go_keeps_original_handoff_semantics_and_clears_selection(self):
        state = create_evolution_state("Original idea", "evo_stateupd02")
        state["evolved_idea"] = "stale candidate text"
        state["selected_concept_id"] = "candidate_111111111111"
        result = {
            "decision": "GO",
            "confidence": "medium",
            "selected_concept_id": None,
            "decision_reasons": ["Original remains preferred"],
            "next_validation": None,
        }
        updated = apply_decision_to_state(state, result, [])
        self.assertEqual(updated["decision"], "GO")
        self.assertIsNone(updated["selected_concept_id"])
        self.assertIsNone(updated["evolved_idea"])
        self.assertIsNone(updated["human_decision"])


if __name__ == "__main__":
    unittest.main()
