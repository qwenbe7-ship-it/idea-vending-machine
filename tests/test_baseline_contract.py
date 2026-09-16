import copy
import unittest

from src.idea_vending.baseline_contract import (
    BASELINE_KEYS,
    create_baseline,
    validate_baseline,
)
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)


class BaselineContractTests(unittest.TestCase):
    def make_graph(self):
        graph = create_evidence_graph("evo_baseline01")
        add_evidence_record(
            graph,
            create_evidence_record(
                evidence_id="ev_baseline01",
                claim_id="claim_baseline01",
                claim="The target workflow creates measurable review cost.",
                source_title="Workflow Evidence",
                source_url="https://example.com/workflow",
                publisher="Example Institute",
                publication_date="2026-08-01",
                retrieved_at="2026-09-16",
                geography="Global",
                population_or_market_definition="Target operations workflow",
                evidence_type="primary_source",
                supports_or_contradicts="supports",
                confidence_tier="A",
                freshness_status="current",
                candidate_ids=[],
                notes="",
                raw_content_untrusted="fixture excerpt",
                provider_metadata={"provider": "fixture"},
                market_size=None,
            ),
        )
        return graph

    def make_baseline(self, **overrides):
        data = {
            "graph": self.make_graph(),
            "evolution_id": "evo_baseline01",
            "raw_idea": "Preserve this original idea verbatim.",
            "problem_framing": "Manual review consumes too much analyst time.",
            "primary_buyer": "Operations lead",
            "user": "Analyst",
            "workflow": "Upload records and review them manually.",
            "value_capture_hypothesis": "Reduce review cost and error exposure.",
            "automation_thesis": "Automate extraction and deterministic checks.",
            "critical_dependencies": ["source data access"],
            "risks": ["false positives"],
            "evidence_claim_ids": ["claim_baseline01"],
            "unknowns": ["buyer willingness to pay"],
            "validation_questions": ["Will the buyer pay for avoided review cost?"],
        }
        data.update(overrides)
        return create_baseline(**data)

    def test_valid_baseline_has_exact_keys_and_content_addressed_id(self):
        first = self.make_baseline()
        second = self.make_baseline()
        self.assertEqual(set(first), BASELINE_KEYS)
        self.assertRegex(first["baseline_id"], r"^baseline_[0-9a-f]{12}$")
        self.assertEqual(first["baseline_id"], second["baseline_id"])

    def test_raw_idea_is_preserved_verbatim(self):
        raw = "  Original wording stays exactly as supplied.  "
        baseline = self.make_baseline(raw_idea=raw)
        self.assertEqual(baseline["raw_idea"], raw)

    def test_tampered_content_addressed_id_is_rejected(self):
        baseline = self.make_baseline()
        baseline["baseline_id"] = "baseline_deadbeef0000"
        with self.assertRaisesRegex(ValueError, "baseline_id does not match"):
            validate_baseline(baseline, self.make_graph())

    def test_unknown_evidence_claim_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown Evidence Graph claim IDs"):
            self.make_baseline(evidence_claim_ids=["claim_missing01"])

    def test_evolution_id_must_match_graph_and_contract(self):
        with self.assertRaisesRegex(ValueError, "evolution_id"):
            self.make_baseline(evolution_id="bad")
        other_graph = create_evidence_graph("evo_other0001")
        with self.assertRaisesRegex(ValueError, "graph evolution_id"):
            self.make_baseline(graph=other_graph)

    def test_list_fields_reject_duplicates_and_empty_items(self):
        with self.assertRaisesRegex(ValueError, "critical_dependencies"):
            self.make_baseline(critical_dependencies=["data", "data"])
        with self.assertRaisesRegex(ValueError, "risks"):
            self.make_baseline(risks=[""])

    def test_unknowns_or_validation_questions_must_remain_explicit(self):
        with self.assertRaisesRegex(ValueError, "unknowns or validation_questions"):
            self.make_baseline(unknowns=[], validation_questions=[])

    def test_mutating_content_without_recomputing_id_is_rejected(self):
        baseline = self.make_baseline()
        mutated = copy.deepcopy(baseline)
        mutated["workflow"] = "Different workflow"
        with self.assertRaisesRegex(ValueError, "baseline_id does not match"):
            validate_baseline(mutated, self.make_graph())


if __name__ == "__main__":
    unittest.main()
