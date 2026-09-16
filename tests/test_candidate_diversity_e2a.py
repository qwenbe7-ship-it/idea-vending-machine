import unittest

from src.idea_vending.candidate_forge import audit_candidate_diversity


DIMS = (
    "primary_buyer",
    "problem_reframe",
    "workflow_after",
    "value_creation_chain",
    "value_capture_model",
    "transformations_used",
    "mechanism_transfer_ids",
)


def candidate(index: int, *, group: str | None = None):
    prefix = group if group is not None else f"unique-{index}"
    return {
        "candidate_id": f"candidate_{index:012x}",
        "primary_buyer": f"buyer-{prefix}",
        "problem_reframe": f"problem-{prefix}",
        "workflow_after": f"workflow-{prefix}",
        "value_creation_chain": {"chain": f"chain-{prefix}"},
        "value_capture_model": f"capture-{prefix}",
        "transformations_used": [f"transform-{prefix}"],
        "mechanism_transfer_ids": [f"transfer-{prefix}"],
    }


class TenCandidateDiversityTests(unittest.TestCase):
    def test_candidate_with_only_two_distinct_peers_is_collapsed(self):
        candidates = [candidate(index, group="same") for index in range(8)]
        candidates.extend([candidate(8), candidate(9)])
        audit = audit_candidate_diversity(candidates)
        self.assertIn("candidate_000000000000", audit["collapsed_candidate_ids"])
        self.assertFalse(audit["diversity_ready"])

    def test_duplicate_problem_workflow_capture_tuple_blocks_diversity(self):
        candidates = [candidate(index) for index in range(10)]
        candidates[1]["problem_reframe"] = candidates[0]["problem_reframe"]
        candidates[1]["workflow_after"] = candidates[0]["workflow_after"]
        candidates[1]["value_capture_model"] = candidates[0]["value_capture_model"]
        audit = audit_candidate_diversity(candidates)
        self.assertFalse(audit["diversity_ready"])
        self.assertTrue(audit.get("duplicate_structural_tuples"))

    def test_fully_distinct_ten_candidate_set_is_ready(self):
        candidates = [candidate(index) for index in range(10)]
        audit = audit_candidate_diversity(candidates)
        self.assertTrue(audit["diversity_ready"])
        self.assertEqual(audit["collapsed_candidate_ids"], [])


if __name__ == "__main__":
    unittest.main()
