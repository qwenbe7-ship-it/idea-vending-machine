import io
import json
import socket
import unittest
from urllib.error import HTTPError

from src.idea_vending.provider_transport import (
    OPENAI_RESPONSES_URL,
    ProviderAuthFailed,
    ProviderHTTPError,
    ProviderInvalidJSON,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderResponseTooLarge,
    ProviderTimeout,
    ResponsesTransport,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    def read(self, amount=-1):
        if amount is None or amount < 0:
            return self._payload
        return self._payload[:amount]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RecordingOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class ProviderTransportTests(unittest.TestCase):
    def test_missing_api_key_is_configuration_failure(self):
        with self.assertRaises(ProviderNotConfigured):
            ResponsesTransport("", 12.0)

    def test_posts_json_only_to_fixed_openai_responses_endpoint(self):
        opener = RecordingOpener(FakeResponse(b'{"id":"resp_1","status":"completed"}'))
        transport = ResponsesTransport("sk-test-secret", 7.5, opener=opener)
        result = transport.post_json({"model": "gpt-5.6-terra", "input": "hello"})

        self.assertEqual(result["id"], "resp_1")
        request, timeout = opener.requests[0]
        self.assertEqual(request.full_url, OPENAI_RESPONSES_URL)
        self.assertEqual(timeout, 7.5)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer sk-test-secret")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"model": "gpt-5.6-terra", "input": "hello"},
        )

    def test_401_and_403_are_normalized_as_auth_failure_without_secret(self):
        for status in (401, 403):
            error = HTTPError(OPENAI_RESPONSES_URL, status, "denied sk-test-secret", {}, io.BytesIO(b""))
            transport = ResponsesTransport(
                "sk-test-secret", 5.0, opener=RecordingOpener(error=error)
            )
            with self.assertRaises(ProviderAuthFailed) as ctx:
                transport.post_json({"model": "gpt-5.6-terra", "input": "hello"})
            self.assertNotIn("sk-test-secret", str(ctx.exception))

    def test_429_is_rate_limit_and_other_http_status_is_generic_http_error(self):
        rate_error = HTTPError(OPENAI_RESPONSES_URL, 429, "rate", {}, io.BytesIO(b""))
        with self.assertRaises(ProviderRateLimited):
            ResponsesTransport("sk-x", 5.0, opener=RecordingOpener(error=rate_error)).post_json({})

        server_error = HTTPError(OPENAI_RESPONSES_URL, 500, "boom", {}, io.BytesIO(b""))
        with self.assertRaises(ProviderHTTPError) as ctx:
            ResponsesTransport("sk-x", 5.0, opener=RecordingOpener(error=server_error)).post_json({})
        self.assertEqual(ctx.exception.status_code, 500)

    def test_timeout_is_normalized(self):
        for error in (TimeoutError("late"), socket.timeout("late")):
            with self.assertRaises(ProviderTimeout):
                ResponsesTransport("sk-x", 1.0, opener=RecordingOpener(error=error)).post_json({})

    def test_invalid_json_is_rejected(self):
        transport = ResponsesTransport(
            "sk-x", 5.0, opener=RecordingOpener(FakeResponse(b"not-json"))
        )
        with self.assertRaises(ProviderInvalidJSON):
            transport.post_json({})

    def test_response_size_is_bounded(self):
        transport = ResponsesTransport(
            "sk-x",
            5.0,
            opener=RecordingOpener(FakeResponse(b"1234567890")),
            max_response_bytes=5,
        )
        with self.assertRaises(ProviderResponseTooLarge):
            transport.post_json({})

    def test_payload_must_be_json_object(self):
        transport = ResponsesTransport(
            "sk-x", 5.0, opener=RecordingOpener(FakeResponse(b"{}"))
        )
        with self.assertRaisesRegex(ValueError, "payload"):
            transport.post_json(["not", "object"])


if __name__ == "__main__":
    unittest.main()
