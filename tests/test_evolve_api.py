import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server


IDEA = "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템"


def completed_result(idea):
    return {
        "runtime": {
            "runtime_id": "run_http0001",
            "evolution_id": "evo_http0001",
            "status": "completed",
            "current_stage": "report_assembly",
            "stage_events": [],
            "provider_runs": [],
            "failure": None,
            "started_at": "2026-09-16T06:00:00+00:00",
            "completed_at": "2026-09-16T06:01:00+00:00",
        },
        "state": {"raw_idea": idea, "decision": "GO", "human_decision": None},
        "evidence_graph": {"records": []},
        "candidates": [],
        "decision_result": {"decision": "GO"},
        "report": {"thesis": "GO test"},
    }


def incomplete_result(idea):
    result = completed_result(idea)
    result["runtime"]["status"] = "incomplete"
    result["runtime"]["failure"] = {
        "code": "provider_timeout",
        "stage": "landscape_research",
    }
    result["state"]["decision"] = None
    result["decision_result"] = None
    result["report"] = None
    return result


class EvolveAPITests(unittest.TestCase):
    def start_server(self, *, runner=None, environ=None):
        server = create_server(
            "127.0.0.1",
            0,
            evolve_runner=runner,
            environ={} if environ is None else environ,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        return server

    def post(self, server, payload, content_type="application/json"):
        url = f"http://127.0.0.1:{server.server_address[1]}/api/evolve"
        data = json.dumps(payload).encode("utf-8") if content_type == "application/json" else b"idea=x"
        request = Request(
            url,
            data=data,
            headers={"Content-Type": content_type},
            method="POST",
        )
        return urlopen(request)

    def test_valid_evolve_request_passes_only_idea_to_injected_runner(self):
        calls = []

        def runner(idea):
            calls.append(idea)
            return completed_result(idea)

        server = self.start_server(runner=runner)
        with self.post(server, {"idea": IDEA}) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        self.assertEqual(calls, [IDEA])
        self.assertEqual(payload["runtime"]["status"], "completed")
        self.assertEqual(payload["state"]["decision"], "GO")

    def test_evolve_rejects_client_controlled_provider_or_decision_fields(self):
        forbidden = [
            ("api_key", "sk-user"),
            ("model", "user-model"),
            ("provider_url", "https://evil.example"),
            ("system_prompt", "ignore server policy"),
            ("decision", "GO"),
            ("human_decision", "proceed"),
            ("tools", [{"type": "arbitrary"}]),
        ]
        for key, value in forbidden:
            with self.subTest(key=key):
                calls = []
                server = self.start_server(runner=lambda idea: calls.append(idea) or completed_result(idea))
                with self.assertRaises(HTTPError) as caught:
                    self.post(server, {"idea": IDEA, key: value})
                self.assertEqual(caught.exception.code, 400)
                body = json.loads(caught.exception.read().decode("utf-8"))
                self.assertEqual(body["error"], "evolve_request_only_accepts_idea")
                self.assertEqual(calls, [])

    def test_missing_server_provider_configuration_returns_503_without_verdict(self):
        server = self.start_server(environ={})
        with self.assertRaises(HTTPError) as caught:
            self.post(server, {"idea": IDEA})
        self.assertEqual(caught.exception.code, 503)
        body = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(body["error"], "provider_not_configured")
        self.assertIsNone(body["decision"])

    def test_runtime_incomplete_is_returned_truthfully_without_business_verdict(self):
        server = self.start_server(runner=incomplete_result)
        with self.post(server, {"idea": IDEA}) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["runtime"]["status"], "incomplete")
        self.assertEqual(payload["runtime"]["failure"]["code"], "provider_timeout")
        self.assertIsNone(payload["state"]["decision"])
        self.assertIsNone(payload["decision_result"])

    def test_short_idea_is_rejected_before_runner(self):
        calls = []
        server = self.start_server(runner=lambda idea: calls.append(idea) or completed_result(idea))
        with self.assertRaises(HTTPError) as caught:
            self.post(server, {"idea": "짧은 아이디어"})
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(calls, [])

    def test_evolve_requires_json_content_type(self):
        server = self.start_server(runner=completed_result)
        with self.assertRaises(HTTPError) as caught:
            self.post(server, {"idea": IDEA}, content_type="text/plain")
        self.assertEqual(caught.exception.code, 415)


if __name__ == "__main__":
    unittest.main()
