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


class DeploymentScriptTests(unittest.TestCase):
    def test_health_only_deployment_is_truthfully_not_ready(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "ok"}),
                "/readyz": (
                    503,
                    {"status": "not_ready", "reason": "provider_not_configured"},
                ),
            }
        )
        result = check_deployment("https://example.test", opener=opener)
        self.assertEqual(result, {"health_ok": True, "ready": False})

    def test_ready_deployment_requires_both_probes(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "ok"}),
                "/readyz": (200, {"status": "ready", "provider": "configured"}),
            }
        )
        result = check_deployment("https://example.test/", opener=opener)
        self.assertEqual(result, {"health_ok": True, "ready": True})
        self.assertEqual(
            [urlparse(url).path for url, _timeout in opener.urls],
            ["/healthz", "/readyz"],
        )

    def test_invalid_health_response_fails_closed(self):
        opener = FakeOpener(
            {
                "/healthz": (200, {"status": "wrong"}),
                "/readyz": (200, {"status": "ready", "provider": "configured"}),
            }
        )
        with self.assertRaises(ValueError):
            check_deployment("https://example.test", opener=opener)


if __name__ == "__main__":
    unittest.main()
