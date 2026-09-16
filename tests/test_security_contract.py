from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecurityContractTests(unittest.TestCase):
    def test_frontend_avoids_html_execution_sinks(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "document.write(", "eval(", "new Function("):
            self.assertNotIn(forbidden, source)
        self.assertIn("textContent", source)

    def test_external_evidence_links_use_safe_rel(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("link.target = '_blank'", source)
        self.assertIn("link.rel = 'noopener noreferrer'", source)

    def test_browser_approval_payload_does_not_send_trusted_decision_fields(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("postJson('/api/evolve/approve', {runtime_id: currentRuntimeId})", source)
        approval_fragment = source.split("/api/evolve/approve", 1)[1]
        self.assertNotIn("human_decision", approval_fragment[:300])
        self.assertNotIn("selected_concept_id", approval_fragment[:300])
        self.assertNotIn("confidence", approval_fragment[:300])

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
