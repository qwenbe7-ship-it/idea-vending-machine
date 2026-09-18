"""Bounded stdlib HTTPS transport for trusted OpenAI-compatible Responses APIs."""

from __future__ import annotations

import json
import socket
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
GROQ_RESPONSES_URL = "https://api.groq.com/openai/v1/responses"
_ALLOWED_RESPONSES_URLS = {OPENAI_RESPONSES_URL, GROQ_RESPONSES_URL}
DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ProviderTransportError(RuntimeError):
    """Base class for sanitized provider transport failures."""


class ProviderNotConfigured(ProviderTransportError):
    pass


class ProviderAuthFailed(ProviderTransportError):
    pass


class ProviderRateLimited(ProviderTransportError):
    pass


class ProviderTimeout(ProviderTransportError):
    pass


class ProviderHTTPError(ProviderTransportError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"provider HTTP request failed with status {status_code}")


class ProviderInvalidJSON(ProviderTransportError):
    pass


class ProviderResponseTooLarge(ProviderTransportError):
    pass


class ResponsesTransport:
    """POST JSON to the fixed OpenAI Responses endpoint with sanitized errors."""

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float,
        *,
        opener: Callable[..., Any] | None = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        responses_url: str = OPENAI_RESPONSES_URL,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderNotConfigured("provider API key is not configured")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
            raise ValueError("timeout_seconds must be a positive number")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive number")
        if responses_url not in _ALLOWED_RESPONSES_URLS:
            raise ValueError("responses_url must be a trusted provider endpoint")
        if not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool):
            raise ValueError("max_response_bytes must be a positive integer")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be a positive integer")

        self._api_key = api_key
        self._timeout_seconds = float(timeout_seconds)
        self._opener = opener or urlopen
        self._max_response_bytes = max_response_bytes
        self._responses_url = responses_url

    def post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            self._responses_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw = response.read(self._max_response_bytes + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthFailed("provider authentication failed") from None
            if exc.code == 429:
                raise ProviderRateLimited("provider rate limit exceeded") from None
            raise ProviderHTTPError(exc.code) from None
        except (TimeoutError, socket.timeout):
            raise ProviderTimeout("provider request timed out") from None
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeout("provider request timed out") from None
            raise ProviderHTTPError(0) from None
        except OSError:
            raise ProviderHTTPError(0) from None

        if len(raw) > self._max_response_bytes:
            raise ProviderResponseTooLarge("provider response exceeded configured size limit")

        try:
            decoded = raw.decode("utf-8")
            result = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ProviderInvalidJSON("provider response was not valid JSON") from None

        if not isinstance(result, dict):
            raise ProviderInvalidJSON("provider response must be a JSON object")
        return result
