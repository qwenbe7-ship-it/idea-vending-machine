from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebContractTests(unittest.TestCase):
    def test_package_controls_exist(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for expected in (
            'id="generate-package"',
            'id="package"',
            'id="spec-preview"',
            'id="design-preview"',
            'id="plan-preview"',
            'data-download="spec.md"',
            'data-download="design.md"',
            'data-download="plan.md"',
        ):
            self.assertIn(expected, html)

    def test_frontend_uses_safe_text_rendering_and_blob_downloads(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", source)
        self.assertIn("textContent", source)
        self.assertIn("new Blob", source)
        self.assertIn("URL.createObjectURL", source)
        self.assertIn("/api/package", source)


if __name__ == "__main__":
    unittest.main()
