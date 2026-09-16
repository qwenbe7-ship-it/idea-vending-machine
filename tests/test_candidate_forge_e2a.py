import unittest

from src.idea_vending.candidate_forge import CANDIDATE_FAMILIES, audit_family_coverage


EXPECTED_FAMILIES = {
    "adjacent_innovation",
    "category_shift",
    "zero_based_reinvention",
    "axion_automation",
    "prevention_shift_left",
    "outcome_execution",
    "workflow_infrastructure",
    "data_decision_asset",
    "buyer_revenue_inversion",
    "compounding_asset",
}


class TenFamilyContractTests(unittest.TestCase):
    def test_candidate_family_vocabulary_is_exactly_ten(self):
        self.assertEqual(CANDIDATE_FAMILIES, EXPECTED_FAMILIES)

    def test_family_coverage_requires_exactly_one_of_every_family(self):
        candidates = [
            {"family": family}
            for family in sorted(EXPECTED_FAMILIES)
        ]
        try:
            audit = audit_family_coverage(candidates)
        except ValueError:
            audit = {"family_ready": False}
        self.assertTrue(audit["family_ready"])

    def test_non_applicable_escape_hatch_is_rejected(self):
        candidates = [{"family": "adjacent_innovation"}]
        rejected = False
        try:
            audit_family_coverage(
                candidates,
                non_applicable_families={
                    "category_shift": "skip",
                    "zero_based_reinvention": "skip",
                    "axion_candidate": "skip",
                },
            )
        except (TypeError, ValueError):
            rejected = True
        self.assertTrue(rejected)


if __name__ == "__main__":
    unittest.main()
