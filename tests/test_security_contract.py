from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityContractTests(unittest.TestCase):
    def test_frontend_does_not_use_inner_html(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", source)

    def test_production_gate_files_exist(self):
        required = [
            ROOT / "scripts" / "verify.py",
            ROOT / ".github" / "workflows" / "production-gate.yml",
        ]
        missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
        self.assertEqual(missing, [])

    def test_server_declares_content_security_policy(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", source)


if __name__ == "__main__":
    unittest.main()
