import unittest

from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)
from src.idea_vending.mechanism_transfer import (
    create_mechanism_transfer,
    validate_mechanism_transfer,
)


def graph_with_claim():
    graph = create_evidence_graph("evo_mechanism01")
    record = create_evidence_record(
        evidence_id="ev_mechanism01",
        claim_id="claim_mechanism01",
        claim="Verified source-domain mechanism evidence",
        source_title="Mechanism Source",
        source_url="https://example.com/mechanism",
        publisher="Example Publisher",
        publication_date="2026-09-01",
        retrieved_at="2026-09-16",
        geography="Global",
        population_or_market_definition="Source domain",
        evidence_type="technology_capability",
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
    source_domain="Insurance underwriting",
    mechanism_name="Risk-based pre-commitment screening",
    mechanism_description="Estimate risk before commitment and alter terms based on the result.",
    source_constraint="The provider cannot inspect every future loss directly.",
    why_it_works_there="Risk signals are converted into a decision before capital is committed.",
    target_equivalent_constraint="The buyer cannot manually verify every transaction risk in time.",
    transfer_logic="Convert pre-transaction signals into a structured risk decision before commitment.",
    value_chain_change="Move review from after-the-fact inspection to pre-commitment prevention.",
    expected_customer_value="Avoid preventable high-risk commitments and reduce review delay.",
    new_risks=["False positives may block valid transactions."],
    supporting_claim_ids=["claim_mechanism01"],
)


class MechanismTransferTests(unittest.TestCase):
    def test_valid_transfer_has_deterministic_trusted_id_and_exact_keys(self):
        graph = graph_with_claim()
        first = create_mechanism_transfer(graph=graph, **VALID_FIELDS)
        second = create_mechanism_transfer(graph=graph, **VALID_FIELDS)
        self.assertEqual(first, second)
        self.assertRegex(first["transfer_id"], r"^transfer_[0-9a-f]{12}$")
        self.assertEqual(
            set(first),
            {
                "transfer_id",
                "source_domain",
                "mechanism_name",
                "mechanism_description",
                "source_constraint",
                "why_it_works_there",
                "target_equivalent_constraint",
                "transfer_logic",
                "value_chain_change",
                "expected_customer_value",
                "new_risks",
                "supporting_claim_ids",
            },
        )

    def test_provider_cannot_supply_transfer_id(self):
        with self.assertRaises(TypeError):
            create_mechanism_transfer(
                graph=graph_with_claim(),
                transfer_id="transfer_providerchosen",
                **VALID_FIELDS,
            )

    def test_validator_rejects_content_valid_transfer_with_tampered_id(self):
        graph = graph_with_claim()
        transfer = create_mechanism_transfer(graph=graph, **VALID_FIELDS)
        transfer["transfer_id"] = "transfer_aaaaaaaaaaaa"
        with self.assertRaises(ValueError):
            validate_mechanism_transfer(transfer, graph)

    def test_missing_causal_explanation_is_rejected(self):
        for field in (
            "source_domain",
            "mechanism_name",
            "mechanism_description",
            "source_constraint",
            "why_it_works_there",
            "target_equivalent_constraint",
            "transfer_logic",
            "value_chain_change",
            "expected_customer_value",
        ):
            fields = dict(VALID_FIELDS)
            fields[field] = ""
            with self.subTest(field=field), self.assertRaises(ValueError):
                create_mechanism_transfer(graph=graph_with_claim(), **fields)

    def test_brand_only_analogy_without_causal_chain_is_rejected(self):
        fields = dict(VALID_FIELDS)
        fields.update(
            mechanism_description="Use Stripe-style UX",
            source_constraint="",
            why_it_works_there="",
            target_equivalent_constraint="",
            transfer_logic="",
            value_chain_change="",
            expected_customer_value="",
        )
        with self.assertRaises(ValueError):
            create_mechanism_transfer(graph=graph_with_claim(), **fields)

    def test_new_risks_must_be_non_empty(self):
        fields = dict(VALID_FIELDS)
        fields["new_risks"] = []
        with self.assertRaises(ValueError):
            create_mechanism_transfer(graph=graph_with_claim(), **fields)

    def test_unknown_supporting_claim_is_rejected(self):
        fields = dict(VALID_FIELDS)
        fields["supporting_claim_ids"] = ["claim_missing01"]
        with self.assertRaises(ValueError):
            create_mechanism_transfer(graph=graph_with_claim(), **fields)

    def test_duplicate_list_items_are_rejected(self):
        fields = dict(VALID_FIELDS)
        fields["new_risks"] = ["Risk A", "Risk A"]
        with self.assertRaises(ValueError):
            create_mechanism_transfer(graph=graph_with_claim(), **fields)


if __name__ == "__main__":
    unittest.main()
