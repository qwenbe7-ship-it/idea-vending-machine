import unittest

from src.idea_vending.evidence_graph import (
    add_evidence_record,
    create_evidence_graph,
    create_evidence_record,
)
from src.idea_vending.reframing import (
    ASSUMPTION_STATUSES,
    ASSUMPTION_TYPES,
    MATERIALITIES,
    TRANSFORMATIONS,
    audit_reframing_readiness,
    create_assumption,
    create_assumption_challenge,
    create_transformation_test,
)


def graph_with_claims():
    graph = create_evidence_graph("evo_reframe01")
    for index, claim_id in enumerate(("claim_support01", "claim_against01"), start=1):
        record = create_evidence_record(
            evidence_id=f"ev_reframe{index:02d}",
            claim_id=claim_id,
            claim=f"Evidence claim {index}",
            source_title=f"Source {index}",
            source_url=f"https://example.com/{index}",
            publisher="Example Publisher",
            publication_date="2026-09-01",
            retrieved_at="2026-09-16",
            geography="Global",
            population_or_market_definition="Example market",
            evidence_type="problem_evidence",
            supports_or_contradicts="supports" if index == 1 else "contradicts",
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


class AssumptionContractTests(unittest.TestCase):
    def test_vocabularies_are_exact(self):
        self.assertEqual(
            ASSUMPTION_TYPES,
            {
                "workflow",
                "customer_behavior",
                "business_model",
                "technology",
                "regulation",
                "distribution",
                "data",
                "economics",
            },
        )
        self.assertEqual(
            ASSUMPTION_STATUSES,
            {"supported", "weak", "contested", "unsupported", "unknown"},
        )
        self.assertEqual(MATERIALITIES, {"none", "minor", "material"})
        self.assertEqual(
            TRANSFORMATIONS,
            {
                "AFTER_TO_BEFORE",
                "REPAIR_TO_PREVENT",
                "SEARCH_TO_PREDICT",
                "ADVISE_TO_EXECUTE",
                "INPUT_TO_OBSERVE",
                "TOOL_TO_WORKFLOW",
                "WORKFLOW_TO_INFRASTRUCTURE",
                "DOCUMENT_TO_DATA",
                "DATA_TO_DECISION",
                "DECISION_TO_ACTION",
                "SERVICE_TO_ASSET",
                "ONE_TIME_TO_COMPOUNDING",
            },
        )

    def test_assumption_has_deterministic_trusted_id_and_known_claim_refs(self):
        graph = graph_with_claims()
        kwargs = dict(
            graph=graph,
            evolution_id="evo_reframe01",
            statement="A human must review every document before action.",
            assumption_type="workflow",
            scope="Current review workflow",
            why_it_exists="Historical quality-control practice",
            supporting_claim_ids=["claim_support01"],
            contradicting_claim_ids=["claim_against01"],
            status="contested",
        )
        first = create_assumption(**kwargs)
        second = create_assumption(**kwargs)
        self.assertEqual(first, second)
        self.assertRegex(first["assumption_id"], r"^assumption_[0-9a-f]{12}$")
        self.assertEqual(first["statement"], kwargs["statement"])

    def test_unknown_claim_id_is_rejected(self):
        with self.assertRaises(ValueError):
            create_assumption(
                graph=graph_with_claims(),
                evolution_id="evo_reframe01",
                statement="A customer must manually start the process.",
                assumption_type="customer_behavior",
                scope="Intake",
                why_it_exists="Legacy form workflow",
                supporting_claim_ids=["claim_missing01"],
                contradicting_claim_ids=[],
                status="unknown",
            )

    def test_provider_cannot_supply_assumption_id(self):
        with self.assertRaises(TypeError):
            create_assumption(
                graph=graph_with_claims(),
                evolution_id="evo_reframe01",
                statement="Documents must remain the unit of work.",
                assumption_type="data",
                scope="Processing",
                why_it_exists="Legacy document systems",
                supporting_claim_ids=[],
                contradicting_claim_ids=[],
                status="unknown",
                assumption_id="assumption_providerchosen",
            )

    def test_challenge_requires_every_causal_field(self):
        assumption = create_assumption(
            graph=graph_with_claims(),
            evolution_id="evo_reframe01",
            statement="Risk review happens after the transaction.",
            assumption_type="workflow",
            scope="Risk workflow",
            why_it_exists="Historical sequencing",
            supporting_claim_ids=[],
            contradicting_claim_ids=[],
            status="unknown",
        )
        challenge = create_assumption_challenge(
            assumption_id=assumption["assumption_id"],
            challenge_question="Does review need to happen after the event?",
            remove_or_invert_test="Move risk calculation before commitment.",
            expected_effect_if_false="Risk is visible before commitment.",
            new_opportunity_if_false="Preventive transaction controls become possible.",
            new_risk_if_false="False positives may block valid transactions.",
        )
        self.assertEqual(challenge["assumption_id"], assumption["assumption_id"])
        with self.assertRaises(ValueError):
            create_assumption_challenge(
                assumption_id=assumption["assumption_id"],
                challenge_question="Does review need to happen after the event?",
                remove_or_invert_test="",
                expected_effect_if_false="Risk is visible earlier.",
                new_opportunity_if_false="Prevention.",
                new_risk_if_false="False positives.",
            )


class TransformationContractTests(unittest.TestCase):
    def test_two_material_transformations_make_generation_ready(self):
        tests = [
            create_transformation_test(
                transformation="AFTER_TO_BEFORE",
                applicable=True,
                reason="The risk signal exists before final commitment.",
                resulting_reframe="Prevent risky commitment instead of reviewing it afterward.",
                materiality="material",
            ),
            create_transformation_test(
                transformation="DOCUMENT_TO_DATA",
                applicable=True,
                reason="Document facts can be normalized into reusable fields.",
                resulting_reframe="Treat the document as a data source rather than the work unit.",
                materiality="material",
            ),
        ]
        audit = audit_reframing_readiness(tests)
        self.assertTrue(audit["generation_ready"])
        self.assertEqual(audit["tested_count"], 2)
        self.assertEqual(len(audit["material_transformations"]), 2)

    def test_one_material_transformation_is_not_ready_without_explicit_original_strong_outcome(self):
        tests = [
            create_transformation_test(
                transformation="TOOL_TO_WORKFLOW",
                applicable=True,
                reason="The buyer wants the task completed, not another tool.",
                resulting_reframe="Embed the capability into the whole workflow.",
                materiality="material",
            )
        ]
        self.assertFalse(audit_reframing_readiness(tests)["generation_ready"])
        audit = audit_reframing_readiness(tests, original_remains_strong=True)
        self.assertTrue(audit["generation_ready"])
        self.assertTrue(audit["original_remains_strong"])

    def test_invalid_transformation_or_materiality_is_rejected(self):
        with self.assertRaises(ValueError):
            create_transformation_test(
                transformation="MAKE_IT_SMARTER",
                applicable=True,
                reason="Invalid vocabulary",
                resulting_reframe="Invalid",
                materiality="material",
            )
        with self.assertRaises(ValueError):
            create_transformation_test(
                transformation="SEARCH_TO_PREDICT",
                applicable=True,
                reason="Try prediction",
                resulting_reframe="Predict instead of search",
                materiality="huge",
            )


if __name__ == "__main__":
    unittest.main()
