"""Render-compatible entrypoint for Idea Vending Machine v0.4.

The verified v0.3 server remains available through ``legacy_app``. Public legacy
symbols are re-exported so existing tests and integrations that import ``app``
keep working. Additive Bridge validation behavior is layered here rather than
rewriting the verified legacy server, while executing ``python app.py`` still
launches the v0.4 autonomous entrypoint used in production.

Security note: the inherited legacy handler remains authoritative for response
headers, including the ``Content-Security-Policy`` contract. Keeping that
contract explicit here prevents the production entrypoint from silently drifting
away from the verified security boundary while avoiding duplicate header logic.
"""

from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from typing import Callable, Mapping

import legacy_app as _legacy_app
from legacy_app import *  # noqa: F401,F403
from legacy_app import _provider_is_configured, _server_address_from_environ, _utcnow_iso
from src.idea_vending.assessment_store import AssessmentStore
from src.idea_vending.bridge_http import BridgeValidationHTTPMixin
from src.idea_vending.bridge_store import BridgeStore


# Add the focused validation-UX asset without rewriting the verified legacy
# static-file handler. The inherited CSP still serves this same-origin script.
_legacy_app._STATIC_FILES["/bridge_validation.js"] = (
    "bridge_validation.js",
    "application/javascript; charset=utf-8",
)


class IdeaVendingHandler(BridgeValidationHTTPMixin, _legacy_app.IdeaVendingHandler):
    """Existing HTTP handler plus safe, actionable Bridge validation responses."""


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    evolve_runner: Callable[[str], dict] | None = None,
    environ: Mapping[str, str] | None = None,
    assessment_store: AssessmentStore | None = None,
    bridge_store: BridgeStore | None = None,
) -> ThreadingHTTPServer:
    """Create the existing server with the additive Bridge validation layer."""
    server = ThreadingHTTPServer((host, port), IdeaVendingHandler)
    server.evolve_runner = evolve_runner  # type: ignore[attr-defined]
    server.evolve_environ = dict(os.environ if environ is None else environ)  # type: ignore[attr-defined]
    server.assessment_store = assessment_store or AssessmentStore()  # type: ignore[attr-defined]
    server.bridge_store = bridge_store or BridgeStore()  # type: ignore[attr-defined]
    return server


def main() -> None:
    """Delegate the production process entrypoint to v0.4 without import cycles."""
    from v04_app import main as autonomous_main

    autonomous_main()


if __name__ == "__main__":
    main()
