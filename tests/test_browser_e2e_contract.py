from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrowserE2EContractTests(unittest.TestCase):
    def test_browser_dependency_is_pinned(self):
        requirement = (ROOT / "requirements-e2e.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(requirement, "playwright==1.63.0")

    def test_browser_verifier_refuses_to_skip_and_covers_required_scenarios(self):
        source = (ROOT / "scripts" / "verify_browser.py").read_text(encoding="utf-8")
        self.assertIn("from playwright.sync_api import", source)
        self.assertIn("FAIL: Playwright test dependency is required", source)
        self.assertIn("chromium.launch", source)
        for marker in (
            "MODIFY",
            "GO",
            "HOLD",
            "KILL",
            "INCOMPLETE",
            "PROVIDER_NOT_CONFIGURED",
            "XSS",
        ):
            self.assertIn(marker, source)
        self.assertIn("BROWSER GREEN WITH EVIDENCE", source)

    def test_browser_gate_uses_deterministic_fake_providers_not_live_credentials(self):
        source = (ROOT / "scripts" / "verify_browser.py").read_text(encoding="utf-8")
        self.assertIn("FakeResearchProvider", source)
        self.assertIn("FakeIdeationProvider", source)
        self.assertIn("FakeEvaluationProvider", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("sk-", source)


if __name__ == "__main__":
    unittest.main()
