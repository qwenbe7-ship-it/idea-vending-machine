import unittest

from src.idea_vending.baseline_contract import create_baseline
from src.idea_vending.candidate_forge import create_candidate
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)
from src.idea_vending.evaluator_contract import EVALUATION_DIMENSIONS, create_critique
from src.idea_vending.independent_evaluator import (
    EVALUATION_REQUEST_KEYS,
    build_evaluation_request,
    ingest_evaluator_output,
)


class IndependentEvaluatorBoundaryTests(unittest.TestCase):
    def make_graph(self):
        graph = create_evidence_graph("evo_boundary01")
        for index, direction in enumerate(("supports", "contradicts"), start=1):
            add_evidence_record(
                graph,
                create_evidence_record(
                    evidence_id=f"ev_bound000{index}",
                    claim_id=f"claim_bound000{index}",
                    claim=f"Boundary evidence {index}",
                    source_title="Source",
                    source_url=f"https://example.com/boundary/{index}",
                    publisher="Publisher",
                    publication_date="2026-09-01",
                    retrieved_at="2026-09-16",
                    geography="Global",
                    population_or_market_definition="Target buyers",
                    evidence_type="buyer_evidence",
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

    def make_baseline(self, graph):
        return create_baseline(
            graph=graph,
            evolution_id="evo_boundary01",
            raw_idea="Original workflow automation idea",
            problem_framing="Manual review is expensive.",
            primary_buyer="Operations lead",
            user="Analyst",
            workflow="Manual document review",
            value_capture_hypothesis="Reduce review cost",
            automation_thesis="Automate extraction and verification",
            critical_dependencies=["source access"],
            risks=["false positives"],
            evidence_claim_ids=["claim_bound0001"],
            unknowns=["buyer WTP"],
            validation_questions=["Will buyers pay?"],
        )

    def make_candidate(self, graph):
        return create_candidate(
            graph=graph,
            family="category_shift",
            name="Preventive Review Engine",
            one_sentence_concept="Prevent costly review failures before commitment.",
            problem_reframe="The problem is late risk discovery, not review speed.",
            primary_buyer="Operations lead",
            user="Analyst",
            job_to_be_done="Avoid preventable high-risk commitments.",
            assumptions_broken=[],
            transformations_used=["AFTER_TO_BEFORE"],
            mechanism_transfer_ids=[],
            workflow_before="Commit then review.",
            workflow_after="Review risk before commitment.",
            value_creation_chain={
                "current_constraint": "Risk is discovered late.",
                "intervention": "Pre-commit risk screening.",
                "workflow_or_incentive_change": "Risky cases are intercepted earlier.",
                "operational_or_economic_effect": "Avoid remediation cost.",
                "buyer_value": "Lower loss and review burden.",
                "value_capture": "Project delivery fee.",
            },
            value_capture_model="Project delivery fee",
            automation_thesis="Automate screening with exception review.",
            defensibility_thesis="Validated decision history improves repeatability.",
            compounding_effect="Decision evidence accumulates.",
            critical_dependencies=["source access"],
            new_risks=["false positives"],
            evidence_claim_ids=["claim_bound0001"],
            unknowns=["buyer WTP"],
            validation_questions=["Will buyers pay?"],
        )

    def dimensions(self):
        return [
            {
                "dimension": name,
                "status": "mixed",
                "rationale": f"Independent assessment of {name}",
                "supporting_claim_ids": ["claim_bound0001"],
                "contradicting_claim_ids": ["claim_bound0002"],
                "material_unknowns": [],
                "blockers": [],
            }
            for name in sorted(EVALUATION_DIMENSIONS)
        ]

    def test_request_has_exact_provider_neutral_shape_and_no_winner(self):
        graph = self.make_graph()
        baseline = self.make_baseline(graph)
        candidate = self.make_candidate(graph)
        request = build_evaluation_request(
            baseline=baseline,
            candidates=[candidate],
            graph=graph,
            candidate_admission_audit={"forge_ready": True},
            feasibility_artifacts={
                baseline["baseline_id"]: {"level": "T4"},
                candidate["candidate_id"]: {"level": "T4"},
            },
            collision_state={"unresolved_material_requests": []},
        )
        self.assertEqual(set(request), EVALUATION_REQUEST_KEYS)
        self.assertNotIn("winner", request)
        self.assertNotIn("selected_concept_id", request)
        self.assertNotIn("decision", request)
        self.assertTrue(request["evaluator_policy"]["official_fields_forbidden"])

    def test_request_is_deep_copied_and_cannot_mutate_callers(self):
        graph = self.make_graph()
        baseline = self.make_baseline(graph)
        candidate = self.make_candidate(graph)
        request = build_evaluation_request(
            baseline=baseline,
            candidates=[candidate],
            graph=graph,
            candidate_admission_audit={"forge_ready": True},
            feasibility_artifacts={},
            collision_state={"unresolved_material_requests": []},
        )
        request["candidates"][0]["name"] = "MUTATED"
        request["baseline"]["problem_framing"] = "MUTATED"
        self.assertNotEqual(candidate["name"], "MUTATED")
        self.assertNotEqual(baseline["problem_framing"], "MUTATED")

    def test_provider_output_with_official_fields_is_rejected(self):
        graph = self.make_graph()
        baseline = self.make_baseline(graph)
        candidate = self.make_candidate(graph)
        with self.assertRaisesRegex(ValueError, "provider output keys"):
            ingest_evaluator_output(
                {"critiques": [], "decision": "GO"},
                graph=graph,
                baseline=baseline,
                candidates=[candidate],
            )

    def test_unknown_target_id_is_rejected(self):
        graph = self.make_graph()
        baseline = self.make_baseline(graph)
        candidate = self.make_candidate(graph)
        critique = create_critique(
            graph=graph,
            target_type="candidate",
            target_id="candidate_deadbeef0000",
            dimensions=self.dimensions(),
            strongest_reason_for="Potential buyer value.",
            strongest_reason_against="Competition remains.",
            unacceptable_conditions=["Buyer economics fail"],
            cheapest_next_validation="Buyer interviews",
            recommendation="hold",
        )
        with self.assertRaisesRegex(ValueError, "unknown evaluator target_id"):
            ingest_evaluator_output(
                {"critiques": [critique]},
                graph=graph,
                baseline=baseline,
                candidates=[candidate],
            )

    def test_valid_output_is_untrusted_deep_copy_with_validated_critiques(self):
        graph = self.make_graph()
        baseline = self.make_baseline(graph)
        candidate = self.make_candidate(graph)
        critique = create_critique(
            graph=graph,
            target_type="candidate",
            target_id=candidate["candidate_id"],
            dimensions=self.dimensions(),
            strongest_reason_for="Potential buyer value.",
            strongest_reason_against="Competition remains.",
            unacceptable_conditions=["Buyer economics fail"],
            cheapest_next_validation="Buyer interviews",
            recommendation="hold",
        )
        raw = {"critiques": [critique]}
        ingested = ingest_evaluator_output(
            raw,
            graph=graph,
            baseline=baseline,
            candidates=[candidate],
        )
        self.assertTrue(ingested["untrusted_provider_output"])
        ingested["critiques"][0]["recommendation"] = "reject"
        self.assertEqual(raw["critiques"][0]["recommendation"], "hold")


if __name__ == "__main__":
    unittest.main()
