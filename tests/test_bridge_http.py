import json
import threading
import unittest
from http.client import HTTPConnection
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import MAX_BODY_BYTES, MAX_BRIDGE_BODY_BYTES, create_server
from src.idea_vending.bridge_contract import BRIDGE_VERSION
from src.idea_vending.bridge_store import BridgeStore
from tests.test_bridge_forge import IDEA, valid_forge_result
from tests.test_evolution_runtime import FakeEvaluationProvider


class BridgeHTTPTests(unittest.TestCase):
    def start_server(self, *, bridge_store=None):
        server = create_server(
            "127.0.0.1",
            0,
            environ={},
            bridge_store=bridge_store or BridgeStore(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.addCleanup(cleanup)
        return server

    def request(self, server, path, payload, *, content_type="application/json"):
        url = f"http://127.0.0.1:{server.server_address[1]}{path}"
        if isinstance(payload, bytes):
            data = payload
        else:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, headers={"Content-Type": content_type}, method="POST")
        try:
            response = urlopen(request)
            status = response.status
            body = response.read()
        except HTTPError as exc:
            status = exc.code
            body = exc.read()
        return status, json.loads(body.decode("utf-8"))

    def oversize_header_request(self, server, path):
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        try:
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(MAX_BRIDGE_BODY_BYTES + 1))
            connection.endheaders()
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

    def forge_request(self, server):
        status, payload = self.request(server, "/api/bridge/forge-request", {"idea": IDEA})
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "forge_requested")
        self.assertEqual(payload["package"]["bridge_version"], BRIDGE_VERSION)
        return payload

    def forge_import(self, server, session_id):
        envelope = {
            "bridge_session_id": session_id,
            "bridge_version": BRIDGE_VERSION,
            "result": valid_forge_result(),
        }
        status, payload = self.request(server, "/api/bridge/forge-import", envelope)
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "forge_validated")
        self.assertEqual(payload["candidate_count"], 10)
        return envelope, payload

    def judge_request(self, server, session_id):
        status, payload = self.request(
            server,
            "/api/bridge/judge-request",
            {"bridge_session_id": session_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], "judge_requested")
        self.assertEqual(payload["package"]["request_type"], "judge")
        return payload

    def make_judge_result(self, judge_package, scenario="go"):
        provider = FakeEvaluationProvider(scenario)
        raw = provider.evaluate(
            {
                "evidence_graph": {"records": judge_package["evidence"]},
                "baseline": judge_package["baseline"],
                "candidates": judge_package["candidates"],
            }
        )
        return {"critiques": raw["critiques"], "additional_evidence": []}

    def test_bridge_body_limit_is_separate_and_larger_than_legacy_api_limit(self):
        self.assertGreater(MAX_BRIDGE_BODY_BYTES, MAX_BODY_BYTES)
        self.assertGreaterEqual(MAX_BRIDGE_BODY_BYTES, 1024 * 1024)

    def test_full_forge_judge_go_round_trip_reaches_existing_approval(self):
        server = self.start_server()
        forge = self.forge_request(server)
        session_id = forge["bridge_session_id"]
        self.forge_import(server, session_id)
        judge = self.judge_request(server, session_id)
        envelope = {
            "bridge_session_id": session_id,
            "bridge_version": BRIDGE_VERSION,
            "result": self.make_judge_result(judge["package"], "go"),
        }
        status, completed = self.request(server, "/api/bridge/judge-import", envelope)
        self.assertEqual(status, 200)
        self.assertEqual(completed["bridge_session_id"], session_id)
        self.assertEqual(completed["runtime"]["status"], "completed")
        self.assertEqual(completed["state"]["decision"], "GO")
        self.assertEqual(len(completed["candidate_reality_assessments"]), 10)

        runtime_id = completed["runtime"]["runtime_id"]
        status, approved = self.request(
            server,
            "/api/evolve/approve",
            {"runtime_id": runtime_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(approved["human_decision"], "proceed")
        self.assertEqual(set(approved["documents"]), {"spec.md", "design.md", "plan.md"})

    def test_out_of_order_unknown_session_and_extra_keys_fail_closed(self):
        server = self.start_server()
        status, payload = self.request(
            server,
            "/api/bridge/judge-request",
            {"bridge_session_id": "br_abcdefghijklmnop"},
        )
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "bridge_session_not_found_or_expired")

        forge = self.forge_request(server)
        session_id = forge["bridge_session_id"]
        status, payload = self.request(
            server,
            "/api/bridge/judge-request",
            {"bridge_session_id": session_id},
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "bridge_state_conflict")

        status, payload = self.request(
            server,
            "/api/bridge/forge-request",
            {"idea": IDEA, "model": "client-controlled"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "forge_request_only_accepts_idea")

    def test_replay_is_idempotent_but_conflicting_replay_is_rejected(self):
        server = self.start_server()
        forge = self.forge_request(server)
        session_id = forge["bridge_session_id"]
        envelope, first = self.forge_import(server, session_id)
        status, replay = self.request(server, "/api/bridge/forge-import", envelope)
        self.assertEqual(status, 200)
        self.assertEqual(replay, first)

        conflicting = json.loads(json.dumps(envelope))
        conflicting["result"]["landscape_research"][0]["claim"] += " changed"
        status, payload = self.request(server, "/api/bridge/forge-import", conflicting)
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "conflicting_forge_replay")

    def test_wrong_content_type_malformed_envelope_and_oversize_bridge_body_are_rejected(self):
        server = self.start_server()
        status, payload = self.request(
            server,
            "/api/bridge/forge-request",
            {"idea": IDEA},
            content_type="text/plain",
        )
        self.assertEqual(status, 415)
        self.assertEqual(payload["error"], "content_type_must_be_application_json")

        status, payload = self.request(server, "/api/bridge/forge-import", {"result": {}})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "bridge_import_invalid")

        status, payload = self.oversize_header_request(server, "/api/bridge/forge-import")
        self.assertEqual(status, 413)
        self.assertEqual(payload["error"], "request_too_large_or_empty")

    def test_forge_invalid_publication_date_returns_safe_actionable_error(self):
        server = self.start_server()
        forge = self.forge_request(server)
        result = valid_forge_result()
        secret_marker = "DO_NOT_ECHO_SECRET_PAYLOAD"
        result["landscape_research"][0]["publication_date"] = "Undated; accessed 2026-09-17"
        result["landscape_research"][0]["raw_excerpt"] = secret_marker
        envelope = {
            "bridge_session_id": forge["bridge_session_id"],
            "bridge_version": BRIDGE_VERSION,
            "result": result,
        }

        status, payload = self.request(server, "/api/bridge/forge-import", envelope)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "bridge_import_invalid")
        error = payload["validation_error"]
        self.assertEqual(error["code"], "bridge_publication_date_invalid")
        self.assertEqual(error["expected_rule"], "YYYY-MM-DD")
        self.assertIn("publication_date", error["message"])
        self.assertTrue(error["repair_instruction"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(secret_marker, serialized)
        self.assertNotIn("Traceback", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_forge_unknown_claim_reference_returns_safe_actionable_error(self):
        server = self.start_server()
        forge = self.forge_request(server)
        result = valid_forge_result()
        result["forge_candidates"]["candidates"][0]["evidence_claim_ids"] = ["bc_prior01"]
        envelope = {
            "bridge_session_id": forge["bridge_session_id"],
            "bridge_version": BRIDGE_VERSION,
            "result": result,
        }

        status, payload = self.request(server, "/api/bridge/forge-import", envelope)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "bridge_import_invalid")
        error = payload["validation_error"]
        self.assertEqual(error["code"], "bridge_claim_reference_unknown")
        self.assertIn("landscape_research", error["expected_rule"])
        self.assertTrue(error["repair_instruction"])
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("Traceback", serialized)
        self.assertNotIn("bc_prior01", serialized)

    def test_api_mode_remains_unconfigured_without_key_even_when_bridge_is_ready(self):
        server = self.start_server()
        status, payload = self.request(server, "/api/evolve", {"idea": IDEA})
        self.assertEqual(status, 503)
        self.assertEqual(payload, {"error": "provider_not_configured", "decision": None})


if __name__ == "__main__":
    unittest.main()
