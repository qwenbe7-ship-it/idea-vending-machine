"""Minimal HTTP server for Idea Vending Machine."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping

from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.assessment_store import AssessmentStore
from src.idea_vending.bridge_request import create_forge_package, create_judge_package
from src.idea_vending.bridge_runtime import (
    bridge_payload_digest,
    validate_and_finalize_judge_import,
    validate_and_run_forge_import,
)
from src.idea_vending.bridge_store import BridgeStore
from src.idea_vending.evolution_handoff import generate_approved_development_package
from src.idea_vending.evolution_runtime import run_evolution
from src.idea_vending.openai_provider import OpenAIProviderConfig, OpenAIResponsesProvider
from src.idea_vending.package_generator import generate_development_package
from src.idea_vending.provider_transport import ResponsesTransport

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_BODY_BYTES = 64 * 1024
MAX_BRIDGE_BODY_BYTES = 1024 * 1024

_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
_API_PATHS = {
    "/api/analyze",
    "/api/package",
    "/api/evolve",
    "/api/evolve/approve",
    "/api/bridge/forge-request",
    "/api/bridge/forge-import",
    "/api/bridge/judge-request",
    "/api/bridge/judge-import",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_is_configured(environ: Mapping[str, str]) -> bool:
    """Validate server-owned provider configuration without contacting the provider."""
    try:
        OpenAIProviderConfig.from_environ(environ)
    except (TypeError, ValueError):
        return False
    return True


def _server_address_from_environ(environ: Mapping[str, str]) -> tuple[str, int]:
    """Resolve the HTTP bind address from trusted server environment variables."""
    host = environ.get("HOST", "127.0.0.1")
    if not isinstance(host, str):
        raise ValueError("HOST must be text")
    host = host.strip() or "127.0.0.1"

    raw_port = environ.get("PORT", "8000")
    if not isinstance(raw_port, str):
        raise ValueError("PORT must be text")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return host, port


def _build_live_evolve_runner(environ: Mapping[str, str]) -> Callable[[str], dict[str, Any]]:
    """Build the server-owned live provider stack without accepting browser configuration."""
    config = OpenAIProviderConfig.from_environ(environ)
    transport = ResponsesTransport(config.api_key, config.timeout_seconds)
    provider = OpenAIResponsesProvider(transport, config)

    def run(idea: str) -> dict[str, Any]:
        return run_evolution(
            idea,
            research_provider=provider,
            ideation_provider=provider,
            evaluation_provider=provider,
            now_provider=_utcnow_iso,
        )

    return run


def _approved_response(record: dict[str, Any]) -> dict[str, Any]:
    state = record["approved_state"]
    return {
        "runtime_id": record["runtime_id"],
        "decision": state["decision"],
        "human_decision": state["human_decision"],
        "documents": record["documents"],
    }


def _forge_import_response(record: dict[str, Any]) -> dict[str, Any]:
    trusted_forge = record.get("trusted_forge")
    candidates = trusted_forge.get("candidates", []) if isinstance(trusted_forge, dict) else []
    return {
        "bridge_session_id": record["bridge_session_id"],
        "state": record["state"],
        "candidate_count": len(candidates),
    }


def _completed_bridge_response(session_id: str, completed: dict[str, Any]) -> dict[str, Any]:
    response = deepcopy(completed)
    response["bridge_session_id"] = session_id
    return response


class IdeaVendingHandler(BaseHTTPRequestHandler):
    server_version = "IdeaVendingMachine/0.3"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'",
        )
        self.end_headers()

    def _send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
        self._send_headers(status, content_type, len(payload))
        self.wfile.write(payload)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _read_json_object(self, *, max_body_bytes: int = MAX_BODY_BYTES) -> dict[str, Any] | None:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_json(415, {"error": "content_type_must_be_application_json"})
            return None

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return None

        if content_length <= 0 or content_length > max_body_bytes:
            self._send_json(413, {"error": "request_too_large_or_empty"})
            return None

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "json_object_required"})
            return None
        return payload

    def _read_idea(self) -> str | None:
        payload = self._read_json_object()
        if payload is None:
            return None
        return payload.get("idea", "")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok"})
            return
        if self.path == "/readyz":
            environ = getattr(self.server, "evolve_environ", {})
            self._send_json(
                200,
                {
                    "status": "ready",
                    "default_mode": "chatgpt_plus_bridge",
                    "modes": {
                        "chatgpt_plus_bridge": "ready",
                        "openai_api": "configured" if _provider_is_configured(environ) else "not_configured",
                    },
                },
            )
            return

        static = _STATIC_FILES.get(self.path)
        if not static:
            self._send_json(404, {"error": "not_found"})
            return
        filename, content_type = static
        body = (WEB_ROOT / filename).read_bytes()
        self._send_bytes(200, body, content_type)

    def _handle_evolve(self) -> None:
        payload = self._read_json_object()
        if payload is None:
            return
        if set(payload) != {"idea"}:
            self._send_json(400, {"error": "evolve_request_only_accepts_idea"})
            return

        idea = payload["idea"]
        try:
            analyze_idea(idea)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        runner = getattr(self.server, "evolve_runner", None)
        if runner is None:
            environ = getattr(self.server, "evolve_environ", {})
            try:
                runner = _build_live_evolve_runner(environ)
            except (TypeError, ValueError):
                self._send_json(
                    503,
                    {"error": "provider_not_configured", "decision": None},
                )
                return

        try:
            result = runner(idea)
        except Exception:
            self._send_json(
                500,
                {"error": "evolution_runtime_failed", "decision": None},
            )
            return
        if not isinstance(result, dict):
            self._send_json(
                500,
                {"error": "evolution_runtime_failed", "decision": None},
            )
            return

        runtime = result.get("runtime")
        if isinstance(runtime, dict) and runtime.get("status") == "completed":
            try:
                self.server.assessment_store.save_completed(result)  # type: ignore[attr-defined]
            except (KeyError, TypeError, ValueError):
                self._send_json(
                    500,
                    {"error": "evolution_runtime_failed", "decision": None},
                )
                return
        self._send_json(200, result)

    def _handle_approve(self) -> None:
        payload = self._read_json_object()
        if payload is None:
            return
        if set(payload) != {"runtime_id"}:
            self._send_json(400, {"error": "approve_request_only_accepts_runtime_id"})
            return
        runtime_id = payload["runtime_id"]
        if not isinstance(runtime_id, str) or not runtime_id.strip():
            self._send_json(400, {"error": "invalid_runtime_id"})
            return

        store = self.server.assessment_store  # type: ignore[attr-defined]
        record = store.get(runtime_id)
        if record is None:
            self._send_json(404, {"error": "assessment_not_found_or_expired"})
            return
        if record["approved"]:
            self._send_json(200, _approved_response(record))
            return

        state = deepcopy(record["result"]["state"])
        decision = state.get("decision")
        if decision not in {"GO", "MODIFY"}:
            self._send_json(
                409,
                {"error": "development_handoff_blocked", "decision": decision},
            )
            return

        state["human_decision"] = "proceed"
        try:
            documents = generate_approved_development_package(state)
            approved = store.mark_approved(runtime_id, state, documents)
        except (KeyError, TypeError, ValueError):
            self._send_json(
                500,
                {"error": "approval_failed", "decision": None},
            )
            return
        self._send_json(200, _approved_response(approved))

    def _handle_bridge_forge_request(self) -> None:
        payload = self._read_json_object()
        if payload is None:
            return
        if set(payload) != {"idea"}:
            self._send_json(400, {"error": "forge_request_only_accepts_idea"})
            return
        idea = payload["idea"]
        try:
            analyze_idea(idea)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        store = self.server.bridge_store  # type: ignore[attr-defined]
        try:
            record = store.create(idea)
            package = create_forge_package(
                idea,
                record["bridge_session_id"],
                _utcnow_iso(),
            )
        except (TypeError, ValueError):
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(
            200,
            {
                "bridge_session_id": record["bridge_session_id"],
                "state": record["state"],
                "package": package,
            },
        )

    def _handle_bridge_forge_import(self) -> None:
        envelope = self._read_json_object(max_body_bytes=MAX_BRIDGE_BODY_BYTES)
        if envelope is None:
            return
        try:
            digest = bridge_payload_digest(envelope)
            session_id = envelope["bridge_session_id"]
        except (KeyError, TypeError, ValueError):
            self._send_json(400, {"error": "bridge_import_invalid"})
            return

        store = self.server.bridge_store  # type: ignore[attr-defined]
        record = store.get(session_id)
        if record is None:
            self._send_json(404, {"error": "bridge_session_not_found_or_expired"})
            return

        existing_digest = record.get("forge_digest")
        if existing_digest is not None:
            if existing_digest != digest:
                self._send_json(409, {"error": "conflicting_forge_replay"})
                return
            self._send_json(200, _forge_import_response(record))
            return
        if record.get("state") != "forge_requested":
            self._send_json(409, {"error": "bridge_state_conflict"})
            return

        try:
            trusted_forge = validate_and_run_forge_import(
                record,
                envelope,
                now_provider=_utcnow_iso,
            )
            saved = store.save_forge(session_id, digest, trusted_forge)
        except ValueError as exc:
            code = str(exc)
            if code == "conflicting_forge_replay":
                self._send_json(409, {"error": code})
            elif code == "bridge_state_invalid":
                self._send_json(409, {"error": "bridge_state_conflict"})
            else:
                self._send_json(400, {"error": "bridge_import_invalid"})
            return
        except Exception:
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(200, _forge_import_response(saved))

    def _handle_bridge_judge_request(self) -> None:
        payload = self._read_json_object()
        if payload is None:
            return
        if set(payload) != {"bridge_session_id"}:
            self._send_json(400, {"error": "judge_request_only_accepts_bridge_session_id"})
            return
        session_id = payload["bridge_session_id"]
        if not isinstance(session_id, str) or not session_id.strip():
            self._send_json(400, {"error": "bridge_session_id_invalid"})
            return

        store = self.server.bridge_store  # type: ignore[attr-defined]
        record = store.get(session_id)
        if record is None:
            self._send_json(404, {"error": "bridge_session_not_found_or_expired"})
            return
        if record.get("state") not in {"forge_validated", "judge_requested"}:
            self._send_json(409, {"error": "bridge_state_conflict"})
            return
        trusted_forge = record.get("trusted_forge")
        try:
            package = create_judge_package(trusted_forge, session_id, _utcnow_iso())
            updated = store.mark_judge_requested(session_id)
        except ValueError:
            self._send_json(409, {"error": "bridge_state_conflict"})
            return
        except Exception:
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(
            200,
            {
                "bridge_session_id": session_id,
                "state": updated["state"],
                "package": package,
            },
        )

    def _handle_bridge_judge_import(self) -> None:
        envelope = self._read_json_object(max_body_bytes=MAX_BRIDGE_BODY_BYTES)
        if envelope is None:
            return
        try:
            digest = bridge_payload_digest(envelope)
            session_id = envelope["bridge_session_id"]
        except (KeyError, TypeError, ValueError):
            self._send_json(400, {"error": "bridge_import_invalid"})
            return

        bridge_store = self.server.bridge_store  # type: ignore[attr-defined]
        record = bridge_store.get(session_id)
        if record is None:
            self._send_json(404, {"error": "bridge_session_not_found_or_expired"})
            return

        existing_digest = record.get("judge_digest")
        if existing_digest is not None:
            if existing_digest != digest:
                self._send_json(409, {"error": "conflicting_judge_replay"})
                return
            completed = record.get("completed_result")
            if not isinstance(completed, dict):
                self._send_json(500, {"error": "bridge_runtime_failed"})
                return
            self._send_json(200, _completed_bridge_response(session_id, completed))
            return
        if record.get("state") != "judge_requested":
            self._send_json(409, {"error": "bridge_state_conflict"})
            return

        try:
            completed = validate_and_finalize_judge_import(
                record,
                envelope,
                now_provider=_utcnow_iso,
            )
            self.server.assessment_store.save_completed(completed)  # type: ignore[attr-defined]
            bridge_store.save_decision(session_id, digest, completed)
        except ValueError as exc:
            code = str(exc)
            if code == "conflicting_judge_replay":
                self._send_json(409, {"error": code})
            elif code == "bridge_state_invalid":
                self._send_json(409, {"error": "bridge_state_conflict"})
            else:
                self._send_json(400, {"error": "bridge_import_invalid"})
            return
        except Exception:
            self._send_json(500, {"error": "bridge_runtime_failed"})
            return
        self._send_json(200, _completed_bridge_response(session_id, completed))

    def do_POST(self) -> None:
        if self.path not in _API_PATHS:
            self._send_json(404, {"error": "not_found"})
            return

        if self.path == "/api/evolve":
            self._handle_evolve()
            return
        if self.path == "/api/evolve/approve":
            self._handle_approve()
            return
        if self.path == "/api/bridge/forge-request":
            self._handle_bridge_forge_request()
            return
        if self.path == "/api/bridge/forge-import":
            self._handle_bridge_forge_import()
            return
        if self.path == "/api/bridge/judge-request":
            self._handle_bridge_judge_request()
            return
        if self.path == "/api/bridge/judge-import":
            self._handle_bridge_judge_import()
            return

        idea = self._read_idea()
        if idea is None:
            return

        try:
            analysis = analyze_idea(idea)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        if self.path == "/api/analyze":
            self._send_json(200, analysis)
            return

        documents = generate_development_package(idea, analysis)
        self._send_json(200, {"analysis": analysis, "documents": documents})


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    evolve_runner: Callable[[str], dict[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
    assessment_store: AssessmentStore | None = None,
    bridge_store: BridgeStore | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), IdeaVendingHandler)
    server.evolve_runner = evolve_runner  # type: ignore[attr-defined]
    server.evolve_environ = dict(os.environ if environ is None else environ)  # type: ignore[attr-defined]
    server.assessment_store = assessment_store or AssessmentStore()  # type: ignore[attr-defined]
    server.bridge_store = bridge_store or BridgeStore()  # type: ignore[attr-defined]
    return server


def main() -> None:
    host, port = _server_address_from_environ(os.environ)
    server = create_server(host, port)
    print(f"Idea Vending Machine running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
