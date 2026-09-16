import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server
from src.idea_vending.evolution_runtime import run_evolution
from tests.test_evolution_runtime import (
    BrokenIdeationProvider,
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
    TimeoutResearchProvider,
)


IDEA = "고객 문의를 자동 분류하고 반복 업무를 예방하는 운영 시스템"


def completed_result(idea, scenario="go"):
    return run_evolution(
        idea,
        research_provider=FakeResearchProvider(),
        ideation_provider=FakeIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider(scenario),
        now_provider=lambda: NOW,
    )


def incomplete_result(idea):
    return run_evolution(
        idea,
        research_provider=TimeoutResearchProvider(),
        ideation_provider=FakeIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider("go"),
        now_provider=lambda: NOW,
    )


def failed_result(idea):
    return run_evolution(
        idea,
        research_provider=FakeResearchProvider(),
        ideation_provider=BrokenIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider("go"),
        now_provider=lambda: NOW,
    )


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

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.addCleanup(cleanup)
        return server

    def post(self, server, payload, content_type="application/json", path="/api/evolve"):
        url = f"http://127.0.0.1:{server.server_address[1]}{path}"
        data = json.dumps(payload).encode("utf-8") if content_type == "application/json" else b"idea=x"
        request = Request(
            url,
            data=data,
            headers={"Content-Type": content_type},
            method="POST",
        )
        return urlopen(request)

    def evolve(self, server, scenario="go"):
        server.evolve_runner = lambda idea: completed_result(idea, scenario)
        with self.post(server, {"idea": IDEA}) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        return payload

    def approve(self, server, runtime_id):
        with self.post(
            server,
            {"runtime_id": runtime_id},
            path="/api/evolve/approve",
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        return payload

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

    def test_completed_evolve_is_persisted_by_trusted_runtime_id(self):
        server = self.start_server(runner=completed_result)
        with self.post(server, {"idea": IDEA}) as response:
            payload = json.loads(response.read().decode("utf-8"))
        runtime_id = payload["runtime"]["runtime_id"]

        record = server.assessment_store.get(runtime_id)

        self.assertIsNotNone(record)
        self.assertEqual(record["result"]["state"], payload["state"])
        self.assertFalse(record["approved"])

    def test_approval_accepts_only_runtime_id(self):
        server = self.start_server(runner=completed_result)
        forbidden = [
            ("decision", "GO"),
            ("human_decision", "proceed"),
            ("selected_concept_id", "candidate_override"),
            ("confidence", "high"),
            ("model", "user-model"),
            ("api_key", "sk-user"),
        ]
        for key, value in forbidden:
            with self.subTest(key=key):
                with self.assertRaises(HTTPError) as caught:
                    self.post(
                        server,
                        {"runtime_id": "run_missing0001", key: value},
                        path="/api/evolve/approve",
                    )
                self.assertEqual(caught.exception.code, 400)
                body = json.loads(caught.exception.read().decode("utf-8"))
                self.assertEqual(body["error"], "approve_request_only_accepts_runtime_id")

    def test_go_approval_sets_server_owned_proceed_and_returns_development_package(self):
        server = self.start_server(runner=completed_result)
        evolved = self.evolve(server, "go")
        runtime_id = evolved["runtime"]["runtime_id"]

        approved = self.approve(server, runtime_id)

        self.assertEqual(approved["runtime_id"], runtime_id)
        self.assertEqual(approved["decision"], "GO")
        self.assertEqual(approved["human_decision"], "proceed")
        self.assertEqual(set(approved["documents"]), {"spec.md", "design.md", "plan.md"})
        self.assertIn(evolved["state"]["raw_idea"], approved["documents"]["spec.md"])

    def test_modify_approval_uses_selected_evolved_idea(self):
        server = self.start_server(runner=completed_result)
        evolved = self.evolve(server, "modify")
        runtime_id = evolved["runtime"]["runtime_id"]
        self.assertEqual(evolved["state"]["decision"], "MODIFY")

        approved = self.approve(server, runtime_id)

        self.assertEqual(approved["decision"], "MODIFY")
        self.assertIn(evolved["state"]["evolved_idea"], approved["documents"]["spec.md"])

    def test_approval_replay_returns_identical_documents(self):
        server = self.start_server(runner=completed_result)
        evolved = self.evolve(server, "go")
        runtime_id = evolved["runtime"]["runtime_id"]

        first = self.approve(server, runtime_id)
        second = self.approve(server, runtime_id)

        self.assertEqual(first, second)
        self.assertEqual(first["documents"], second["documents"])

    def test_hold_and_kill_cannot_be_approved(self):
        for scenario in ("hold", "kill"):
            with self.subTest(scenario=scenario):
                server = self.start_server(runner=completed_result)
                evolved = self.evolve(server, scenario)
                runtime_id = evolved["runtime"]["runtime_id"]
                self.assertEqual(evolved["state"]["decision"], scenario.upper())

                with self.assertRaises(HTTPError) as caught:
                    self.post(
                        server,
                        {"runtime_id": runtime_id},
                        path="/api/evolve/approve",
                    )
                self.assertEqual(caught.exception.code, 409)
                body = json.loads(caught.exception.read().decode("utf-8"))
                self.assertEqual(body["error"], "development_handoff_blocked")
                self.assertEqual(body["decision"], scenario.upper())

    def test_unknown_or_expired_runtime_is_not_approvable(self):
        server = self.start_server(runner=completed_result)
        with self.assertRaises(HTTPError) as caught:
            self.post(
                server,
                {"runtime_id": "run_missing0001"},
                path="/api/evolve/approve",
            )
        self.assertEqual(caught.exception.code, 404)
        body = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual(body["error"], "assessment_not_found_or_expired")

    def test_incomplete_and_failed_results_are_never_persisted(self):
        for runner, expected_status in ((incomplete_result, "incomplete"), (failed_result, "failed")):
            with self.subTest(expected_status=expected_status):
                server = self.start_server(runner=runner)
                with self.post(server, {"idea": IDEA}) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                runtime_id = payload["runtime"]["runtime_id"]
                self.assertEqual(payload["runtime"]["status"], expected_status)
                self.assertIsNone(server.assessment_store.get(runtime_id))


if __name__ == "__main__":
    unittest.main()
