import unittest

from src.idea_vending.candidate_forge import (
    CANDIDATE_FAMILIES,
    VALUE_CHAIN_KEYS,
    create_candidate,
)
from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)


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


if __name__ == "__main__":
    unittest.main()
