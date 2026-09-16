from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductionGateContractTests(unittest.TestCase):
    def test_workflow_has_unit_and_real_browser_layers(self):
        workflow = (ROOT / ".github" / "workflows" / "production-gate.yml").read_text(encoding="utf-8")
        self.assertIn("verify:", workflow)
        self.assertIn("browser-e2e:", workflow)
        self.assertIn("needs: verify", workflow)
        self.assertIn("actions/checkout@v7", workflow)
        self.assertIn("actions/setup-python@v7", workflow)
        self.assertIn("python -m pip install -r requirements-e2e.txt", workflow)
        self.assertIn("python -m playwright install chromium --with-deps", workflow)
        self.assertIn("python scripts/verify_browser.py", workflow)

    def test_browser_job_does_not_receive_live_provider_credentials(self):
        workflow = (ROOT / ".github" / "workflows" / "production-gate.yml").read_text(encoding="utf-8")
        browser_job = workflow.split("browser-e2e:", 1)[1] if "browser-e2e:" in workflow else ""
        self.assertNotIn("OPENAI_API_KEY", browser_job)
        self.assertNotIn("secrets.", browser_job)


if __name__ == "__main__":
    unittest.main()
