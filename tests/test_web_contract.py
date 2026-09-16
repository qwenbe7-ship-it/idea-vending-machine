from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebContractTests(unittest.TestCase):
    def test_executive_decision_first_sections_exist(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for expected in (
            'id="evolve-submit"',
            'id="runtime-progress"',
            'id="executive-decision"',
            'id="candidate-grid"',
            'id="evidence-report"',
            'id="detailed-report"',
            'id="approve-direction"',
            'id="package"',
            'id="spec-preview"',
            'id="design-preview"',
            'id="plan-preview"',
            'data-download="spec.md"',
            'data-download="design.md"',
            'data-download="plan.md"',
        ):
            self.assertIn(expected, html)
        self.assertIn("아이디어 진화시키기", html)

    def test_frontend_uses_primary_evolve_and_server_owned_approval(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("/api/evolve", source)
        self.assertIn("/api/evolve/approve", source)
        self.assertIn("{runtime_id: currentRuntimeId}", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, decision", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, confidence", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, selected", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, human_decision", source)

    def test_frontend_uses_safe_dom_and_blob_downloads(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "document.write("):
            self.assertNotIn(forbidden, source)
        self.assertIn("textContent", source)
        self.assertIn("replaceChildren", source)
        self.assertIn("new Blob", source)
        self.assertIn("URL.createObjectURL", source)
        self.assertIn("noopener noreferrer", source)

    def test_runtime_and_reality_evaluation_are_rendered_from_server_payload(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for expected in (
            "stage_events",
            "candidate_reality_assessments",
            "dimension_statuses",
            "hard_or_material_blockers",
            "material_unknowns",
            "evidence_graph",
            "detailed_analysis",
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
