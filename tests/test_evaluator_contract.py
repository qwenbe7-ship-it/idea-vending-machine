import copy
import unittest

from src.idea_vending.evaluator_contract import (
    DIMENSION_KEYS,
    EVALUATION_DIMENSIONS,
    RECOMMENDATIONS,
    STATUSES,
    create_critique,
    validate_critique,
    validate_dimension_assessment,
)
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)


class EvaluatorContractTests(unittest.TestCase):
    def make_graph(self):
        graph = create_evidence_graph("evo_eval0001")
        for index, direction in enumerate(("supports", "contradicts"), start=1):
            add_evidence_record(
                graph,
                create_evidence_record(
                    evidence_id=f"ev_eval000{index}",
                    claim_id=f"claim_eval000{index}",
                    claim=f"Decision evidence {index}",
                    source_title="Source",
                    source_url=f"https://example.com/{index}",
                    publisher="Publisher",
                    publication_date="2026-08-01",
                    retrieved_at="2026-09-16",
                    geography="Global",
                    population_or_market_definition="Decision market",
                    evidence_type="primary_source",
                    supports_or_contradicts=direction,
                    confidence_tier="A",
                    freshness_status="current",
                    candidate_ids=[],
                    notes="",
                    raw_content_untrusted="fixture",
                    provider_metadata={"provider": "fixture"},
                    market_size=None,
                ),
            )
        return graph

    def dimension(self, name, status="strong"):
        return {
            "dimension": name,
            "status": status,
            "rationale": f"Assessment for {name}",
            "supporting_claim_ids": ["claim_eval0001"],
            "contradicting_claim_ids": ["claim_eval0002"],
            "material_unknowns": [],
            "blockers": [],
        }

    def dimensions(self):
        return [self.dimension(name) for name in sorted(EVALUATION_DIMENSIONS)]

    def make_critique(self, **overrides):
        data = {
            "graph": self.make_graph(),
            "target_type": "candidate",
            "target_id": "candidate_123456789abc",
            "dimensions": self.dimensions(),
            "strongest_reason_for": "Evidence supports buyer value.",
            "strongest_reason_against": "Competition remains material.",
            "unacceptable_conditions": ["Buyer economics fail"],
            "cheapest_next_validation": "Interview five qualified buyers.",
            "recommendation": "advance",
        }
        data.update(overrides)
        return create_critique(**data)

    def test_vocabularies_are_exact(self):
        self.assertEqual(STATUSES, {"strong", "mixed", "weak", "unknown"})
        self.assertEqual(RECOMMENDATIONS, {"advance", "revise", "hold", "reject"})
        self.assertEqual(len(EVALUATION_DIMENSIONS), 10)

    def test_valid_dimension_has_exact_keys(self):
        item = self.dimension("problem_evidence")
        validate_dimension_assessment(item, self.make_graph())
        self.assertEqual(set(item), DIMENSION_KEYS)

    def test_invalid_status_and_unknown_claim_are_rejected(self):
        bad = self.dimension("problem_evidence", status="excellent")
        with self.assertRaisesRegex(ValueError, "status"):
            validate_dimension_assessment(bad, self.make_graph())
        bad = self.dimension("problem_evidence")
        bad["supporting_claim_ids"] = ["claim_missing"]
        with self.assertRaisesRegex(ValueError, "unknown Evidence Graph claim IDs"):
            validate_dimension_assessment(bad, self.make_graph())

    def test_critique_requires_every_dimension_exactly_once(self):
        missing = self.dimensions()[:-1]
        with self.assertRaisesRegex(ValueError, "every evaluation dimension"):
            self.make_critique(dimensions=missing)
        duplicate = self.dimensions()
        duplicate[-1] = copy.deepcopy(duplicate[0])
        with self.assertRaisesRegex(ValueError, "every evaluation dimension"):
            self.make_critique(dimensions=duplicate)

    def test_provider_official_decision_fields_are_rejected(self):
        critique = self.make_critique()
        for forbidden in ("decision", "confidence", "selected_concept_id", "score", "rank", "winner"):
            mutated = dict(critique)
            mutated[forbidden] = "provider-owned"
            with self.assertRaisesRegex(ValueError, "critique keys"):
                validate_critique(mutated, self.make_graph())

    def test_recommendation_is_advisory_closed_vocabulary(self):
        for recommendation in RECOMMENDATIONS:
            self.make_critique(recommendation=recommendation)
        with self.assertRaisesRegex(ValueError, "recommendation"):
            self.make_critique(recommendation="GO")

    def test_blocker_requires_evidence_and_closed_materiality(self):
        item = self.dimension("problem_evidence")
        item["blockers"] = [{
            "reason": "Regulatory prohibition",
            "materiality": "hard",
            "evidence_claim_ids": ["claim_eval0002"],
            "resolvable": False,
        }]
        validate_dimension_assessment(item, self.make_graph())
        item["blockers"][0]["materiality"] = "fatal-ish"
        with self.assertRaisesRegex(ValueError, "materiality"):
            validate_dimension_assessment(item, self.make_graph())


if __name__ == "__main__":
    unittest.main()
