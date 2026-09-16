import unittest

from src.idea_vending.analyzer import analyze_idea


class AnalyzeIdeaTests(unittest.TestCase):
    def test_rejects_ideas_shorter_than_ten_characters(self):
        with self.assertRaises(ValueError):
            analyze_idea("짧은 아이디어")

    def test_returns_required_fields(self):
        result = analyze_idea("부동산 계약서를 올리면 위험조항을 찾아주는 프로그램")
        required = {
            "problem",
            "customer",
            "automation_level",
            "feasibility_level",
            "risks",
            "mvp_scope",
            "acceptance_criteria",
        }
        self.assertTrue(required.issubset(result.keys()))

    def test_same_input_returns_same_output(self):
        idea = "고객 문의 이메일을 분류하고 답변 초안을 자동으로 만드는 도구"
        self.assertEqual(analyze_idea(idea), analyze_idea(idea))

    def test_levels_use_expected_scales(self):
        result = analyze_idea("업로드된 영수증에서 항목을 추출하고 표로 정리하는 자동화 도구")
        self.assertRegex(result["automation_level"], r"^A[0-5]$")
        self.assertRegex(result["feasibility_level"], r"^T[1-5]$")
        self.assertGreaterEqual(len(result["acceptance_criteria"]), 3)


if __name__ == "__main__":
    unittest.main()
