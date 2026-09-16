import unittest

from src.idea_vending.ideation_contract import (
    IDEATION_OPERATIONS,
    create_ideation_request,
    run_ideation_operation,
)


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.payload


class IdeationContractTests(unittest.TestCase):
    def test_operation_vocabulary_is_exact(self):
        self.assertEqual(
            IDEATION_OPERATIONS,
            {
                "extract_assumptions",
                "challenge_assumptions",
                "propose_reframes",
                "discover_mechanisms",
                "forge_candidates",
            },
        )

    def test_request_has_exact_provider_neutral_shape(self):
        request = create_ideation_request(
            operation="forge_candidates",
            objective="Generate structurally different candidate concepts.",
            raw_idea="Analyze contracts with AI before a transaction.",
            problem_context={"root_constraint": "Risk appears too late"},
            assumption_context=[{"statement": "Review happens after commitment"}],
            evidence_summary=[{"claim_id": "claim_example01", "claim": "Example"}],
            allowed_transformations=["AFTER_TO_BEFORE", "DOCUMENT_TO_DATA"],
            required_output_schema={"type": "candidate_set"},
            constraints=["Do not select a winner", "Label unsupported claims as hypotheses"],
        )
        self.assertEqual(
            set(request),
            {
                "operation",
                "objective",
                "raw_idea",
                "problem_context",
                "assumption_context",
                "evidence_summary",
                "allowed_transformations",
                "required_output_schema",
                "constraints",
            },
        )

    def test_invalid_operation_is_rejected(self):
        with self.assertRaises(ValueError):
            create_ideation_request(
                operation="choose_winner",
                objective="Choose a winner",
                raw_idea="An idea",
                problem_context={},
                assumption_context=[],
                evidence_summary=[],
                allowed_transformations=[],
                required_output_schema={},
                constraints=["No decision authority"],
            )

    def test_provider_output_is_untrusted_copy_and_cannot_mutate_request(self):
        payload = {
            "candidate_id": "provider_chosen_id",
            "decision": "GO",
            "content": [{"idea": "Provider suggestion"}],
        }
        provider = FakeProvider(payload)
        request = create_ideation_request(
            operation="forge_candidates",
            objective="Generate candidates",
            raw_idea="Automate a risky manual workflow.",
            problem_context={},
            assumption_context=[],
            evidence_summary=[],
            allowed_transformations=["TOOL_TO_WORKFLOW"],
            required_output_schema={"type": "untrusted_provider_payload"},
            constraints=["No decision authority"],
        )
        before = dict(request)
        result = run_ideation_operation(provider, request)
        self.assertEqual(request, before)
        self.assertEqual(result, payload)
        self.assertIsNot(result, payload)
        result["decision"] = "KILL"
        self.assertEqual(payload["decision"], "GO")

    def test_non_dictionary_provider_output_is_rejected(self):
        provider = FakeProvider("free-form text")
        request = create_ideation_request(
            operation="propose_reframes",
            objective="Reframe the problem",
            raw_idea="Automate a manual workflow.",
            problem_context={},
            assumption_context=[],
            evidence_summary=[],
            allowed_transformations=["TOOL_TO_WORKFLOW"],
            required_output_schema={"type": "object"},
            constraints=["Return structured data"],
        )
        with self.assertRaises(ValueError):
            run_ideation_operation(provider, request)


if __name__ == "__main__":
    unittest.main()
