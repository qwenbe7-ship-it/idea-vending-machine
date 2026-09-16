import json
import threading
import unittest
from urllib.request import Request, urlopen

from app import create_server
from tests.test_evolve_api import IDEA, completed_result


class AutonomousHTTPTests(unittest.TestCase):
    def start_server(self, *, runner=None, environ=None):
        server = create_server(
            "127.0.0.1",
            0,
            evolve_runner=runner,
            environ={} if environ is None else environ,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.addCleanup(cleanup)
        return server

    def post_evolve(self, server, payload):
        request = Request(
            f"http://127.0.0.1:{server.server_address[1]}/api/evolve",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def get_ready(self, server):
        with urlopen(f"http://127.0.0.1:{server.server_address[1]}/readyz") as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_completed_autonomous_response_has_server_derived_summary(self):
        server = self.start_server(runner=completed_result)
        status, payload = self.post_evolve(server, {"idea": IDEA})

        self.assertEqual(status, 200)
        summary = payload["automation_summary"]
        self.assertEqual(summary["mode"], "autonomous_due_diligence")
        self.assertTrue(summary["research_completed"])
        self.assertEqual(summary["evidence_count"], len(payload["evidence_graph"]["records"]))
        self.assertEqual(
            summary["contradicting_evidence_count"],
            sum(
                1
                for record in payload["evidence_graph"]["records"]
                if record.get("supports_or_contradicts") == "contradicts"
            ),
        )
        self.assertEqual(summary["candidate_count"], 10)
        self.assertEqual(summary["independent_critique_count"], len(payload["critiques"]))
        self.assertEqual(summary["decision"], payload["state"]["decision"])
        self.assertEqual(summary["runtime_id"], payload["runtime"]["runtime_id"])

    def test_runner_cannot_supply_trusted_automation_summary(self):
        def runner(idea):
            result = completed_result(idea)
            result["automation_summary"] = {
                "mode": "provider_controlled",
                "candidate_count": 999,
                "decision": "GO",
            }
            return result

        server = self.start_server(runner=runner)
        _, payload = self.post_evolve(server, {"idea": IDEA})

        self.assertEqual(payload["automation_summary"]["mode"], "autonomous_due_diligence")
        self.assertEqual(payload["automation_summary"]["candidate_count"], 10)
        self.assertEqual(payload["automation_summary"]["decision"], payload["state"]["decision"])

    def test_readiness_prefers_autonomous_mode_only_when_server_provider_is_configured(self):
        unconfigured = self.start_server(environ={})
        status, ready = self.get_ready(unconfigured)
        self.assertEqual(status, 200)
        self.assertEqual(ready["default_mode"], "chatgpt_plus_bridge")
        self.assertEqual(ready["modes"]["openai_api"], "not_configured")

        configured = self.start_server(environ={"OPENAI_API_KEY": "sk-test"})
        status, ready = self.get_ready(configured)
        self.assertEqual(status, 200)
        self.assertEqual(ready["default_mode"], "autonomous_due_diligence")
        self.assertEqual(ready["modes"]["autonomous_due_diligence"], "ready")
        self.assertEqual(ready["modes"]["openai_api"], "configured")


if __name__ == "__main__":
    unittest.main()
