"""Sanitized public deployment verifier for Idea Vending Machine."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen


DEFAULT_TIMEOUT_SECONDS = 10.0


def _request_json(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    """Fetch one JSON object while normalizing HTTP error responses."""
    try:
        response = urlopen(url, timeout=timeout)
        status = response.status
        body = response.read()
    except HTTPError as exc:
        status = exc.code
        body = exc.read()
    except (TimeoutError, URLError) as exc:
        raise ValueError("deployment_probe_unreachable") from exc

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("deployment_probe_invalid_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("deployment_probe_json_object_required")
    return status, payload


def _validated_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url_required")
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url_must_be_http_or_https")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("base_url_must_not_include_path_query_or_fragment")
    return normalized


def check_deployment(
    base_url: str,
    *,
    opener: Callable[[str, float], tuple[int, dict[str, Any]]] = _request_json,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, bool]:
    """Check public liveness and Bridge-first readiness without provider calls."""
    base = _validated_base_url(base_url)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout_must_be_positive")

    health_status, health_payload = opener(f"{base}/healthz", float(timeout))
    if health_status != 200 or health_payload != {"status": "ok"}:
        raise ValueError("deployment_health_failed")

    ready_status, ready_payload = opener(f"{base}/readyz", float(timeout))
    if ready_status != 200 or set(ready_payload) != {"status", "default_mode", "modes"}:
        raise ValueError("deployment_readiness_unexpected")
    if ready_payload.get("status") != "ready":
        raise ValueError("deployment_readiness_unexpected")
    if ready_payload.get("default_mode") != "chatgpt_plus_bridge":
        raise ValueError("deployment_readiness_unexpected")

    modes = ready_payload.get("modes")
    if not isinstance(modes, dict) or set(modes) != {"chatgpt_plus_bridge", "openai_api"}:
        raise ValueError("deployment_readiness_unexpected")
    if modes.get("chatgpt_plus_bridge") != "ready":
        raise ValueError("deployment_readiness_unexpected")
    if modes.get("openai_api") not in {"configured", "not_configured"}:
        raise ValueError("deployment_readiness_unexpected")

    return {
        "health_ok": True,
        "ready": True,
        "api_configured": modes["openai_api"] == "configured",
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("FAIL: usage: python scripts/verify_deployment.py <base-url>", file=sys.stderr)
        return 2

    try:
        result = check_deployment(args[0])
    except Exception:
        print("FAIL: deployment verification failed", file=sys.stderr)
        return 1

    print("PASS: deployment health")
    print("PASS: ChatGPT Plus Bridge readiness")
    if result["api_configured"]:
        print("PASS: optional OpenAI API mode configured")
    else:
        print("INFO: optional OpenAI API mode not configured")
    print("DEPLOYMENT BRIDGE READY WITH EVIDENCE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
