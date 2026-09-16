import re
import unittest

from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.package_generator import generate_development_package


class PackageGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.idea = "업로드된 영수증에서 항목을 추출하고 표로 정리하는 자동화 도구"
        self.analysis = analyze_idea(self.idea)

    def test_returns_exact_required_documents(self):
        documents = generate_development_package(self.idea, self.analysis)
        self.assertEqual(set(documents), {"spec.md", "design.md", "plan.md"})
        self.assertTrue(all(isinstance(value, str) and value.strip() for value in documents.values()))

    def test_same_input_is_byte_identical(self):
        first = generate_development_package(self.idea, self.analysis)
        second = generate_development_package(self.idea, self.analysis)
        self.assertEqual(first, second)

    def test_all_documents_share_same_project_id(self):
        documents = generate_development_package(self.idea, self.analysis)
        ids = []
        for content in documents.values():
            match = re.search(r"Project ID: `([^`]+)`", content)
            self.assertIsNotNone(match)
            ids.append(match.group(1))
        self.assertEqual(len(set(ids)), 1)

    def test_spec_contains_acceptance_criteria_verbatim(self):
        spec = generate_development_package(self.idea, self.analysis)["spec.md"]
        for criterion in self.analysis["acceptance_criteria"]:
            self.assertIn(criterion, spec)

    def test_documents_have_no_placeholder_markers(self):
        documents = generate_development_package(self.idea, self.analysis)
        for filename, content in documents.items():
            upper = content.upper()
            self.assertNotIn("TBD", upper, filename)
            self.assertNotIn("TODO", upper, filename)


if __name__ == "__main__":
    unittest.main()
