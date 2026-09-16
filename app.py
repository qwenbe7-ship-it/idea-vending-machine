"""Minimal HTTP server for Idea Vending Machine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping

from src.idea_vending.analyzer import analyze_idea
from src.idea_vending.evolution_runtime import run_evolution
from src.idea_vending.openai_provider import OpenAIProviderConfig, OpenAIResponsesProvider
from src.idea_vending.package_generator import generate_development_package
from src.idea_vending.provider_transport import ResponsesTransport

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_BODY_BYTES = 64 * 1024

_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
_API_PATHS = {"/api/analyze", "/api/package", "/api/evolve"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def _read_json_object(self) -> dict[str, Any] | None:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._send_json(415, {"error": "content_type_must_be_application_json"})
            return None

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return None

        if content_length <= 0 or content_length > MAX_BODY_BYTES:
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
        self._send_json(200, result)

    def do_POST(self) -> None:
        if self.path not in _API_PATHS:
            self._send_json(404, {"error": "not_found"})
            return

        if self.path == "/api/evolve":
            self._handle_evolve()
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
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), IdeaVendingHandler)
    server.evolve_runner = evolve_runner  # type: ignore[attr-defined]
    server.evolve_environ = dict(os.environ if environ is None else environ)  # type: ignore[attr-defined]
    return server


def main() -> None:
    server = create_server()
    print("Idea Vending Machine running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
