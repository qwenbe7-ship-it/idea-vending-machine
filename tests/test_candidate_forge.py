import unittest

from src.idea_vending.candidate_forge import (
    CANDIDATE_FAMILIES,
    VALUE_CHAIN_KEYS,
    audit_candidate_diversity,
    audit_candidate_set,
    audit_family_coverage,
    create_candidate,
    create_collision_research_request,
    validate_causal_value_chain,
)
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)
from src.idea_vending.mechanism_transfer import create_mechanism_transfer
from src.idea_vending.reframing import create_transformation_test


def graph_with_claim():
    graph = create_evidence_graph("evo_candidate01")
    record = create_evidence_record(
        evidence_id="ev_candidate01",
        claim_id="claim_candidate01",
        claim="Customers experience costly review delays.",
        source_title="Customer Evidence",
        source_url="https://example.com/customer",
        publisher="Example Publisher",
        publication_date="2026-09-01",
        retrieved_at="2026-09-16",
        geography="Global",
        population_or_market_definition="Target buyers",
        evidence_type="buyer_evidence",
        supports_or_contradicts="supports",
        confidence_tier="A",
        freshness_status="current",
        candidate_ids=[],
        notes="",
        raw_content_untrusted="raw",
        provider_metadata={},
        market_size=None,
    )
    add_evidence_record(graph, record)
    return graph


VALID_FIELDS = dict(
    family="category_shift",
    name="Preventive Transaction Risk Engine",
    one_sentence_concept="Estimate transaction risk before commitment and alter the workflow accordingly.",
    problem_reframe="The problem is not slow review but preventable risk discovered too late.",
    primary_buyer="Transaction operator",
    user="Risk reviewer",
    job_to_be_done="Prevent avoidable high-risk commitments without slowing every transaction.",
    assumptions_broken=["assumption_123456789abc"],
    transformations_used=["AFTER_TO_BEFORE", "DOCUMENT_TO_DATA"],
    mechanism_transfer_ids=["transfer_123456789abc"],
    workflow_before="Commit first, review documents later, then remediate problems.",
    workflow_after="Normalize signals, estimate risk, and gate commitment before execution.",
    value_creation_chain={
        "current_constraint": "Risk is discovered after commitment.",
        "intervention": "Pre-commitment risk estimation.",
        "workflow_or_incentive_change": "High-risk cases are intercepted before commitment.",
        "operational_or_economic_effect": "Avoided remediation work and lower preventable loss.",
        "buyer_value": "Faster safe decisions and fewer expensive mistakes.",
        "value_capture": "Charge for verified risk-reduction outcomes or project delivery.",
    },
    value_capture_model="Project-based deployment plus outcome-linked service fees.",
    automation_thesis="Most evidence normalization and pre-screening can be automated with exception review.",
    defensibility_thesis="Verified workflow data and decision history improve future validation and switching cost.",
    compounding_effect="Validated decisions accumulate into reusable workflow intelligence.",
    critical_dependencies=["Reliable source data", "Clear exception policy"],
    new_risks=["False positives could block valid transactions."],
    evidence_claim_ids=["claim_candidate01"],
    unknowns=["Actual willingness to pay for prevention remains unverified."],
    validation_questions=["Will target buyers pay to prevent risk before commitment?"],
)


def candidate_fields_for_family(family, index, *, transfer_id=None):
    fields = dict(VALID_FIELDS)
    fields.update(
        family=family,
        name=f"Candidate {index}",
        one_sentence_concept=f"Distinct candidate concept {index}",
        primary_buyer=f"Buyer {index}",
        problem_reframe=f"Distinct root problem framing {index}",
        workflow_after=f"Distinct target workflow {index}",
        value_capture_model=f"Distinct value capture model {index}",
        transformations_used=[
            ["AFTER_TO_BEFORE", "DOCUMENT_TO_DATA"],
            ["TOOL_TO_WORKFLOW", "DATA_TO_DECISION"],
            ["INPUT_TO_OBSERVE", "DECISION_TO_ACTION"],
            ["SERVICE_TO_ASSET", "ONE_TIME_TO_COMPOUNDING"],
        ][index - 1],
        mechanism_transfer_ids=[transfer_id or f"transfer_{index:012d}"],
        value_creation_chain={
            "current_constraint": f"Constraint {index}",
            "intervention": f"Intervention {index}",
            "workflow_or_incentive_change": f"Workflow change {index}",
            "operational_or_economic_effect": f"Economic effect {index}",
            "buyer_value": f"Buyer value {index}",
            "value_capture": f"Value capture {index}",
        },
    )
    return fields


def candidate_for_family(graph, family, index):
    return create_candidate(graph=graph, **candidate_fields_for_family(family, index))


def admission_fixture():
    graph = graph_with_claim()
    families = [
        "adjacent_innovation",
        "category_shift",
        "zero_based_reinvention",
        "axion_candidate",
    ]
    transfers = []
    candidates = []
    for index, family in enumerate(families, start=1):
        transfer = create_mechanism_transfer(
            graph=graph,
            source_domain=f"Source domain {index}",
            mechanism_name=f"Mechanism {index}",
            mechanism_description=f"Mechanism description {index}",
            source_constraint=f"Source constraint {index}",
            why_it_works_there=f"Why it works {index}",
            target_equivalent_constraint=f"Target constraint {index}",
            transfer_logic=f"Transfer logic {index}",
            value_chain_change=f"Value-chain change {index}",
            expected_customer_value=f"Expected customer value {index}",
            new_risks=[f"Transfer risk {index}"],
            supporting_claim_ids=["claim_candidate01"],
        )
        transfers.append(transfer)
        candidates.append(
            create_candidate(
                graph=graph,
                **candidate_fields_for_family(
                    family, index, transfer_id=transfer["transfer_id"]
                ),
            )
        )
    transformations = [
        create_transformation_test(
            transformation="AFTER_TO_BEFORE",
            applicable=True,
            reason="Risk signals exist before commitment.",
            resulting_reframe="Prevent risk before commitment.",
            materiality="material",
        ),
        create_transformation_test(
            transformation="DOCUMENT_TO_DATA",
            applicable=True,
            reason="Documents can be normalized into reusable fields.",
            resulting_reframe="Use structured data rather than documents as the work unit.",
            materiality="material",
        ),
    ]
    return graph, candidates, transfers, transformations


class CandidateContractTests(unittest.TestCase):
    def test_family_and_value_chain_vocabularies_are_exact(self):
        self.assertEqual(
            CANDIDATE_FAMILIES,
            {
                "adjacent_innovation",
                "category_shift",
                "zero_based_reinvention",
                "axion_candidate",
            },
        )
        self.assertEqual(
            VALUE_CHAIN_KEYS,
            {
                "current_constraint",
                "intervention",
                "workflow_or_incentive_change",
                "operational_or_economic_effect",
                "buyer_value",
                "value_capture",
            },
        )

    def test_valid_candidate_has_deterministic_trusted_id_and_exact_keys(self):
        graph = graph_with_claim()
        first = create_candidate(graph=graph, **VALID_FIELDS)
        second = create_candidate(graph=graph, **VALID_FIELDS)
        self.assertEqual(first, second)
        self.assertRegex(first["candidate_id"], r"^candidate_[0-9a-f]{12}$")
        self.assertNotIn("score", first)
        self.assertNotIn("winner", first)
        self.assertNotIn("decision", first)
        self.assertNotIn("approved", first)

    def test_provider_cannot_supply_candidate_id_or_score(self):
        with self.assertRaises(TypeError):
            create_candidate(
                graph=graph_with_claim(),
                candidate_id="candidate_provider",
                **VALID_FIELDS,
            )
        with self.assertRaises(TypeError):
            create_candidate(graph=graph_with_claim(), score=99, **VALID_FIELDS)

    def test_invalid_family_is_rejected(self):
        fields = dict(VALID_FIELDS)
        fields["family"] = "best_idea"
        with self.assertRaises(ValueError):
            create_candidate(graph=graph_with_claim(), **fields)

    def test_unknown_evidence_claim_is_rejected(self):
        fields = dict(VALID_FIELDS)
        fields["evidence_claim_ids"] = ["claim_missing01"]
        with self.assertRaises(ValueError):
            create_candidate(graph=graph_with_claim(), **fields)

    def test_invalid_transformation_is_rejected(self):
        fields = dict(VALID_FIELDS)
        fields["transformations_used"] = ["MAKE_IT_BETTER"]
        with self.assertRaises(ValueError):
            create_candidate(graph=graph_with_claim(), **fields)

    def test_value_creation_chain_requires_every_exact_link(self):
        fields = dict(VALID_FIELDS)
        chain = dict(fields["value_creation_chain"])
        chain.pop("buyer_value")
        fields["value_creation_chain"] = chain
        with self.assertRaises(ValueError):
            create_candidate(graph=graph_with_claim(), **fields)

    def test_hypothesis_candidate_may_have_no_evidence_claims_if_unknowns_remain_explicit(self):
        fields = dict(VALID_FIELDS)
        fields["evidence_claim_ids"] = []
        candidate = create_candidate(graph=graph_with_claim(), **fields)
        self.assertEqual(candidate["evidence_claim_ids"], [])
        self.assertTrue(candidate["unknowns"])

    def test_list_fields_reject_duplicates_and_empty_items(self):
        fields = dict(VALID_FIELDS)
        fields["critical_dependencies"] = ["Reliable data", "Reliable data"]
        with self.assertRaises(ValueError):
            create_candidate(graph=graph_with_claim(), **fields)


class DiversityAndCausalGateTests(unittest.TestCase):
    def test_structurally_distinct_four_family_set_is_diversity_ready(self):
        graph = graph_with_claim()
        candidates = [
            candidate_for_family(graph, "adjacent_innovation", 1),
            candidate_for_family(graph, "category_shift", 2),
            candidate_for_family(graph, "zero_based_reinvention", 3),
            candidate_for_family(graph, "axion_candidate", 4),
        ]
        audit = audit_candidate_diversity(candidates)
        self.assertTrue(audit["diversity_ready"])
        self.assertEqual(audit["collapsed_candidate_ids"], [])
        self.assertEqual(len(audit["pairwise_differences"]), 6)

    def test_cosmetic_variants_collapse_even_when_names_differ(self):
        graph = graph_with_claim()
        candidates = []
        for index, family in enumerate(
            [
                "adjacent_innovation",
                "category_shift",
                "zero_based_reinvention",
                "axion_candidate",
            ],
            start=1,
        ):
            fields = dict(VALID_FIELDS)
            fields["family"] = family
            fields["name"] = f"Marketing Name {index}"
            fields["one_sentence_concept"] = f"Marketing copy {index}"
            candidates.append(create_candidate(graph=graph, **fields))
        audit = audit_candidate_diversity(candidates)
        self.assertFalse(audit["diversity_ready"])
        self.assertEqual(len(audit["collapsed_candidate_ids"]), 4)

    def test_causal_gate_rejects_missing_link_in_mutated_candidate(self):
        candidate = create_candidate(graph=graph_with_claim(), **VALID_FIELDS)
        candidate["value_creation_chain"]["buyer_value"] = ""
        with self.assertRaises(ValueError):
            validate_causal_value_chain(candidate)


class FamilyCoverageTests(unittest.TestCase):
    def test_all_four_generated_families_are_ready(self):
        graph = graph_with_claim()
        candidates = [
            candidate_for_family(graph, "adjacent_innovation", 1),
            candidate_for_family(graph, "category_shift", 2),
            candidate_for_family(graph, "zero_based_reinvention", 3),
            candidate_for_family(graph, "axion_candidate", 4),
        ]
        audit = audit_family_coverage(candidates)
        self.assertTrue(audit["family_ready"])
        self.assertEqual(audit["missing_families"], [])

    def test_non_applicable_family_requires_reason(self):
        graph = graph_with_claim()
        candidates = [candidate_for_family(graph, "adjacent_innovation", 1)]
        audit = audit_family_coverage(
            candidates,
            non_applicable_families={
                "category_shift": "No category shift survives the current evidence.",
                "zero_based_reinvention": "The workflow is already close to zero-based design.",
                "axion_candidate": "Automation economics are not applicable to this case.",
            },
        )
        self.assertTrue(audit["family_ready"])
        with self.assertRaises(ValueError):
            audit_family_coverage(
                candidates,
                non_applicable_families={
                    "category_shift": "",
                    "zero_based_reinvention": "Reason",
                    "axion_candidate": "Reason",
                },
            )

    def test_family_cannot_be_generated_and_non_applicable(self):
        graph = graph_with_claim()
        candidate = candidate_for_family(graph, "category_shift", 2)
        with self.assertRaises(ValueError):
            audit_family_coverage(
                [candidate],
                non_applicable_families={"category_shift": "Contradictory state"},
            )


class CollisionResearchRequestTests(unittest.TestCase):
    def test_request_is_deterministic_and_has_exact_contract(self):
        kwargs = dict(
            candidate_id="candidate_123456789abc",
            question="Does a materially similar prior-art product already exist?",
            reason="A similar product could remove differentiation.",
            materiality="material",
            suggested_category="prior_art",
        )
        first = create_collision_research_request(**kwargs)
        second = create_collision_research_request(**kwargs)
        self.assertEqual(first, second)
        self.assertRegex(first["research_request_id"], r"^collision_[0-9a-f]{12}$")
        self.assertEqual(
            set(first),
            {
                "research_request_id",
                "candidate_id",
                "question",
                "reason",
                "materiality",
                "suggested_category",
            },
        )

    def test_invalid_materiality_or_category_is_rejected(self):
        with self.assertRaises(ValueError):
            create_collision_research_request(
                candidate_id="candidate_123456789abc",
                question="Question?",
                reason="Reason",
                materiality="critical",
                suggested_category="prior_art",
            )
        with self.assertRaises(ValueError):
            create_collision_research_request(
                candidate_id="candidate_123456789abc",
                question="Question?",
                reason="Reason",
                materiality="material",
                suggested_category="hype_check",
            )


class CandidateSetAdmissionTests(unittest.TestCase):
    def test_valid_set_reports_each_gate_and_never_selects_a_winner(self):
        graph, candidates, transfers, transformations = admission_fixture()
        audit = audit_candidate_set(
            graph,
            candidates,
            transformations,
            transfers,
        )
        self.assertEqual(
            set(audit),
            {
                "schema_ready",
                "evidence_ready",
                "reframe_ready",
                "mechanism_ready",
                "causal_ready",
                "diversity_ready",
                "family_ready",
                "unknowns_ready",
                "forge_ready",
            },
        )
        self.assertTrue(all(audit.values()))
        for forbidden in ("best_candidate", "winner", "score", "verdict", "decision"):
            self.assertNotIn(forbidden, audit)

    def test_reframe_failure_blocks_forge_without_hiding_other_gate_results(self):
        graph, candidates, transfers, _ = admission_fixture()
        one_transformation = [
            create_transformation_test(
                transformation="AFTER_TO_BEFORE",
                applicable=True,
                reason="Only one material reframe tested.",
                resulting_reframe="Prevent rather than repair.",
                materiality="material",
            )
        ]
        audit = audit_candidate_set(
            graph,
            candidates,
            one_transformation,
            transfers,
        )
        self.assertFalse(audit["reframe_ready"])
        self.assertFalse(audit["forge_ready"])
        self.assertTrue(audit["schema_ready"])
        self.assertTrue(audit["evidence_ready"])

    def test_unknown_mechanism_reference_blocks_mechanism_gate(self):
        graph, candidates, transfers, transformations = admission_fixture()
        audit = audit_candidate_set(
            graph,
            candidates,
            transformations,
            transfers[:-1],
        )
        self.assertFalse(audit["mechanism_ready"])
        self.assertFalse(audit["forge_ready"])

    def test_every_candidate_must_keep_unknowns_or_validation_questions_explicit(self):
        graph, candidates, transfers, transformations = admission_fixture()
        fields = candidate_fields_for_family(
            "axion_candidate", 4, transfer_id=transfers[3]["transfer_id"]
        )
        fields["unknowns"] = []
        fields["validation_questions"] = []
        candidates[-1] = create_candidate(graph=graph, **fields)
        audit = audit_candidate_set(
            graph,
            candidates,
            transformations,
            transfers,
        )
        self.assertFalse(audit["unknowns_ready"])
        self.assertFalse(audit["forge_ready"])


if __name__ == "__main__":
    unittest.main()
