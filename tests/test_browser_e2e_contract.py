from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrowserE2EContractTests(unittest.TestCase):
    def test_browser_dependency_is_pinned(self):
        requirement = (ROOT / "requirements-e2e.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(requirement, "playwright==1.63.0")

    def test_browser_verifier_refuses_to_skip_and_covers_required_bridge_scenarios(self):
        source = (ROOT / "scripts" / "verify_browser.py").read_text(encoding="utf-8")
        self.assertIn("from playwright.sync_api import", source)
        self.assertIn("FAIL: Playwright test dependency is required", source)
        self.assertIn("chromium.launch", source)
        for marker in (
            "BRIDGE_FORGE_EXPORT",
            "BRIDGE_FORGE_IMPORT",
            "BRIDGE_JUDGE_EXPORT",
            "BRIDGE_JUDGE_IMPORT",
            "BRIDGE_GO_APPROVAL",
            "BRIDGE_MODIFY_APPROVAL",
            "BRIDGE_HOLD_BLOCKED",
            "BRIDGE_KILL_BLOCKED",
            "BRIDGE_MALFORMED_IMPORT",
            "BRIDGE_WRONG_SESSION",
            "BRIDGE_REPLAY",
            "BRIDGE_XSS",
            "BRIDGE_READY_WITHOUT_API",
        ):
            self.assertIn(marker, source)
        self.assertIn("BROWSER GREEN WITH EVIDENCE", source)

    def test_browser_gate_uses_deterministic_bridge_fixtures_not_live_credentials(self):
        source = (ROOT / "scripts" / "verify_browser.py").read_text(encoding="utf-8")
        self.assertIn("valid_forge_result", source)
        self.assertIn("FakeEvaluationProvider", source)
        self.assertNotIn("OpenAIResponsesProvider", source)
        self.assertNotIn("OPENAI_API_KEY", source)
        self.assertNotIn("sk-", source)


if __name__ == "__main__":
    unittest.main()
