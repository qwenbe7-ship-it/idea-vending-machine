import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def post_json(self, path, payload):
        request = Request(
            self.url(path),
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urlopen(request)

    def test_index_loads(self):
        with urlopen(self.url("/")) as response:
            body = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("아이디어 자판기", body)

    def test_valid_analysis_request_returns_required_fields(self):
        with self.post_json(
            "/api/analyze",
            {"idea": "업로드된 영수증에서 항목을 추출하고 표로 정리하는 자동화 도구"},
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        self.assertIn("automation_level", result)
        self.assertIn("acceptance_criteria", result)

    def test_valid_package_request_returns_analysis_and_documents(self):
        with self.post_json(
            "/api/package",
            {"idea": "업로드된 영수증에서 항목을 추출하고 표로 정리하는 자동화 도구"},
        ) as response:
            result = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.status, 200)
        self.assertIn("analysis", result)
        self.assertEqual(set(result["documents"]), {"spec.md", "design.md", "plan.md"})
        self.assertIn("acceptance_criteria", result["analysis"])

    def test_short_idea_returns_400(self):
        with self.assertRaises(HTTPError) as caught:
            self.post_json("/api/analyze", {"idea": "짧은 아이디어"})
        self.assertEqual(caught.exception.code, 400)

    def test_short_idea_on_package_returns_400(self):
        with self.assertRaises(HTTPError) as caught:
            self.post_json("/api/package", {"idea": "짧은 아이디어"})
        self.assertEqual(caught.exception.code, 400)

    def test_non_json_request_returns_415(self):
        request = Request(
            self.url("/api/analyze"),
            data=b"idea=hello",
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 415)

    def test_non_json_package_request_returns_415(self):
        request = Request(
            self.url("/api/package"),
            data=b"idea=hello",
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 415)


if __name__ == "__main__":
    unittest.main()
