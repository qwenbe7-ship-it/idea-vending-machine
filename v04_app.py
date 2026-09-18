"""Idea Vending Machine v0.4 autonomous due-diligence entrypoint.

This module intentionally reuses the verified v0.3 HTTP/Bridge/approval surface
and overrides only the autonomous product path. Bridge remains a fallback.
"""

from __future__ import annotations

from copy import deepcopy
import os
from http.server import ThreadingHTTPServer
from typing import Any, Callable, Mapping

import app as legacy_app
from src.idea_vending.assessment_store import AssessmentStore
from src.idea_vending.automation_summary import derive_automation_summary
from src.idea_vending.bridge_store import BridgeStore
from src.idea_vending.evolution_runtime import run_evolution
from src.idea_vending.groq_provider import GroqProviderConfig, GroqResponsesProvider
from src.idea_vending.openai_provider import OpenAIProviderConfig, OpenAIResponsesProvider
from src.idea_vending.provider_transport import GROQ_RESPONSES_URL, ResponsesTransport

AUTONOMOUS_UI_SCRIPT = legacy_app.ROOT / "web/v04.js"
_AUTONOMOUS_SCRIPT_TAG = '  <script src="/v04.js" defer></script>\n'


def _configured_provider_name(environ: Mapping[str, str]) -> str | None:
    if str(environ.get("GROQ_API_KEY", "")).strip():
        return "groq"
    if str(environ.get("OPENAI_API_KEY", "")).strip():
        return "openai"
    return None


def _build_autonomous_runner(environ: Mapping[str, str]) -> Callable[[str], dict[str, Any]]:
    """Build three isolated server-owned provider roles from trusted config.

    Groq GPT-OSS 120B is the primary autonomous provider. OpenAI remains an
    optional compatibility fallback. The ChatGPT Plus Bridge remains available
    when neither API key is configured.
    """
    provider_name = _configured_provider_name(environ)
    if provider_name == "groq":
        config = GroqProviderConfig.from_environ(environ)

        def provider() -> GroqResponsesProvider:
            transport = ResponsesTransport(
                config.api_key,
                config.timeout_seconds,
                responses_url=GROQ_RESPONSES_URL,
            )
            return GroqResponsesProvider(transport, config)
    elif provider_name == "openai":
        config = OpenAIProviderConfig.from_environ(environ)

        def provider() -> OpenAIResponsesProvider:
            transport = ResponsesTransport(config.api_key, config.timeout_seconds)
            return OpenAIResponsesProvider(transport, config)
    else:
        raise ValueError("no autonomous provider API key is configured")

    research_provider = provider()
    ideation_provider = provider()
    evaluation_provider = provider()

    def run(idea: str) -> dict[str, Any]:
        return run_evolution(
            idea,
            research_provider=research_provider,
            ideation_provider=ideation_provider,
            evaluation_provider=evaluation_provider,
            now_provider=legacy_app._utcnow_iso,
        )

    return run


class AutonomousIdeaVendingHandler(legacy_app.IdeaVendingHandler):
    """v0.4 handler that promotes autonomous due diligence to the product path."""

    server_version = "IdeaVendingMachine/0.4"

    def do_GET(self) -> None:
        if self.path == "/v04.js":
            body = AUTONOMOUS_UI_SCRIPT.read_bytes()
            self._send_bytes(200, body, "application/javascript; charset=utf-8")
            return

        if self.path == "/":
            html = (legacy_app.WEB_ROOT / "index.html").read_text(encoding="utf-8")
            if "/v04.js" not in html:
                html = html.replace("</body>", f"{_AUTONOMOUS_SCRIPT_TAG}</body>", 1)
            self._send_bytes(200, html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if self.path != "/readyz":
            super().do_GET()
            return

        environ = getattr(self.server, "evolve_environ", {})
        injected_runner = getattr(self.server, "evolve_runner", None)
        provider_name = _configured_provider_name(environ)
        configured = callable(injected_runner) or provider_name is not None
        self._send_json(
            200,
            {
                "status": "ready",
                "default_mode": (
                    "autonomous_due_diligence" if configured else "chatgpt_plus_bridge"
                ),
                "modes": {
                    "autonomous_due_diligence": "ready" if configured else "not_configured",
                    "chatgpt_plus_bridge": "ready",
                    "groq_api": "configured" if provider_name == "groq" else "not_configured",
                    "openai_api": "configured" if provider_name == "openai" else "not_configured",
                },
                "autonomous_provider": (
                    "injected" if callable(injected_runner) else provider_name
                ),
            },
        )

    def _handle_evolve(self) -> None:
        payload = self._read_json_object()
        if payload is None:
            return
        if set(payload) != {"idea"}:
            self._send_json(400, {"error": "evolve_request_only_accepts_idea"})
            return

        idea = payload["idea"]
        try:
            legacy_app.analyze_idea(idea)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        runner = getattr(self.server, "evolve_runner", None)
        if runner is None:
            environ = getattr(self.server, "evolve_environ", {})
            try:
                runner = _build_autonomous_runner(environ)
            except (TypeError, ValueError):
                self._send_json(
                    503,
                    {"error": "provider_not_configured", "decision": None},
                )
                return

        try:
            raw_result = runner(idea)
        except Exception:
            self._send_json(
                500,
                {"error": "evolution_runtime_failed", "decision": None},
            )
            return
        if not isinstance(raw_result, dict):
            self._send_json(
                500,
                {"error": "evolution_runtime_failed", "decision": None},
            )
            return

        # Never preserve a provider/runner supplied automation summary. Derive it
        # only from the trusted runtime output after all existing gates have run.
        result = deepcopy(raw_result)
        result["automation_summary"] = derive_automation_summary(result)

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


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    evolve_runner: Callable[[str], dict[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
    assessment_store: AssessmentStore | None = None,
    bridge_store: BridgeStore | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), AutonomousIdeaVendingHandler)
    server.evolve_runner = evolve_runner  # type: ignore[attr-defined]
    server.evolve_environ = dict(os.environ if environ is None else environ)  # type: ignore[attr-defined]
    server.assessment_store = assessment_store or AssessmentStore()  # type: ignore[attr-defined]
    server.bridge_store = bridge_store or BridgeStore()  # type: ignore[attr-defined]
    return server


def main() -> None:
    host, port = legacy_app._server_address_from_environ(os.environ)
    server = create_server(host, port)
    print(f"Idea Vending Machine v0.4 running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
