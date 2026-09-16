import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app import _server_address_from_environ, create_server


class DeploymentReadinessTests(unittest.TestCase):
    def start_server(self, *, environ=None):
        server = create_server(
            "127.0.0.1",
            0,
            environ={} if environ is None else environ,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(2)

        self.addCleanup(cleanup)
        return server

    def get_json(self, server, path):
        url = f"http://127.0.0.1:{server.server_address[1]}{path}"
        try:
            response = urlopen(url)
            status = response.status
            body = response.read()
        except HTTPError as exc:
            status = exc.code
            body = exc.read()
        return status, json.loads(body.decode("utf-8"))

    def test_healthz_is_passive_liveness(self):
        server = self.start_server(environ={})
        status, payload = self.get_json(server, "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_readyz_is_200_for_bridge_without_api_configuration(self):
        server = self.start_server(environ={})
        status, payload = self.get_json(server, "/readyz")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["default_mode"], "chatgpt_plus_bridge")
        self.assertEqual(payload["modes"]["chatgpt_plus_bridge"], "ready")
        self.assertEqual(payload["modes"]["openai_api"], "not_configured")

    def test_readyz_reports_api_mode_independently_when_configured(self):
        server = self.start_server(environ={"OPENAI_API_KEY": "test-key"})
        status, payload = self.get_json(server, "/readyz")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["default_mode"], "chatgpt_plus_bridge")
        self.assertEqual(payload["modes"]["chatgpt_plus_bridge"], "ready")
        self.assertEqual(payload["modes"]["openai_api"], "configured")

    def test_server_address_defaults_to_localhost_8000(self):
        self.assertEqual(_server_address_from_environ({}), ("127.0.0.1", 8000))

    def test_server_address_uses_render_host_and_port(self):
        self.assertEqual(
            _server_address_from_environ({"HOST": "0.0.0.0", "PORT": "10000"}),
            ("0.0.0.0", 10000),
        )

    def test_invalid_port_is_rejected(self):
        for value in ("zero", "0", "65536"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _server_address_from_environ({"PORT": value})


if __name__ == "__main__":
    unittest.main()
