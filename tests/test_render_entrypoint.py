import sys
import types
import unittest

import app


class RenderEntrypointTests(unittest.TestCase):
    def test_legacy_render_start_command_delegates_to_v04_main(self):
        calls = []
        fake_v04 = types.ModuleType("v04_app")
        fake_v04.main = lambda: calls.append("v04")

        class FakeServer:
            def serve_forever(self):
                return None

            def server_close(self):
                return None

        original_module = sys.modules.get("v04_app")
        original_create_server = app.create_server
        app.create_server = lambda *_args, **_kwargs: FakeServer()
        sys.modules["v04_app"] = fake_v04
        try:
            app.main()
        finally:
            app.create_server = original_create_server
            if original_module is None:
                sys.modules.pop("v04_app", None)
            else:
                sys.modules["v04_app"] = original_module

        self.assertEqual(calls, ["v04"])


if __name__ == "__main__":
    unittest.main()
