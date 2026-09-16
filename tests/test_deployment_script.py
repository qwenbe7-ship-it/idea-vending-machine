import unittest
from urllib.parse import urlparse

from scripts.verify_deployment import check_deployment


class FakeOpener:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append((url, timeout))
        path = urlparse(url).path
        return self.responses[path]


def bridge_ready_payload(api_mode="not_configured"):
    return {
        "status": "ready",
        "default_mode": "chatgpt_plus_bridge",
        "modes": {
            "chatgpt_plus_bridge": "ready",
            "openai_api": api_mode,
        },
    }


class DeploymentScriptTests(unittest.TestCase):
    def test_bridge_ready_without_api_configuration(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "ok"}),
                "/readyz": (200, bridge_ready_payload()),
            }
        )
        result = check_deployment("https://example.test", opener=opener)
        self.assertEqual(
            result,
            {"health_ok": True, "ready": True, "api_configured": False},
        )

    def test_bridge_ready_reports_optional_api_mode_independently(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "ok"}),
                "/readyz": (200, bridge_ready_payload("configured")),
            }
        )
        result = check_deployment("https://example.test/", opener=opener)
        self.assertEqual(
            result,
            {"health_ok": True, "ready": True, "api_configured": True},
        )
        self.assertEqual(
            [urlparse(url).path for url, _timeout in opener.urls],
            ["/healthz", "/readyz"],
        )

    def test_legacy_provider_only_readiness_is_rejected(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "ok"}),
                "/readyz": (200, {"status": "ready", "provider": "configured"}),
            }
        )
        with self.assertRaises(ValueError):
            check_deployment("https://example.test", opener=opener)

    def test_invalid_health_response_fails_closed(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "wrong"}),
                "/readyz": (200, bridge_ready_payload()),
            }
        )
        with self.assertRaises(ValueError):
            check_deployment("https://example.test", opener=opener)


if __name__ == "__main__":
    unittest.main()
