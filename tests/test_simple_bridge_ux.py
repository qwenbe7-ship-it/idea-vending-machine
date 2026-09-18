from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SimpleBridgeUxTests(unittest.TestCase):
    def test_default_bridge_flow_is_copy_run_paste_continue(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="bridge-advanced"', html)
        self.assertIn('>분석 시작</button>', html)
        self.assertNotIn('>ChatGPT Plus로 분석</button>', html)
        self.assertEqual(html.count('>ChatGPT에서 계속하기</a>'), 2)
        self.assertIn("<strong>① ChatGPT에서 Forge 실행</strong>", html)
        self.assertIn("<strong>② ChatGPT가 생성한 최종 JSON만 붙여넣기</strong>", html)
        self.assertIn("<strong>② Judge가 생성한 최종 JSON만 붙여넣기</strong>", html)
        self.assertIn(">③ 결과 검증하고 계속</button>", html)
        self.assertIn(">③ 최종 검증하고 판단 생성</button>", html)
        self.assertEqual(html.count('href="https://chatgpt.com/"'), 2)
        self.assertIn('별도의 새 ChatGPT 대화', html)

        advanced_at = html.index('id="bridge-advanced"')
        for technical_id in (
            'id="bridge-session"',
            'id="copy-forge-json"',
            'id="download-forge-json"',
            'id="forge-package"',
            'id="forge-result-file"',
            'id="copy-judge-json"',
            'id="download-judge-json"',
            'id="judge-package"',
            'id="judge-result-file"',
        ):
            self.assertGreater(html.index(technical_id), advanced_at, technical_id)

    def test_copy_has_fallback_and_empty_result_is_friendly(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        for expected in (
            "async function copyTextWithFallback(",
            "function legacyClipboardCopy(",
            "document.execCommand('copy')",
            "ChatGPT 결과를 붙여넣어 주세요.",
            "ChatGPT 결과가 올바른 JSON이 아닙니다.",
            "/api/bridge/forge-import",
            "/api/bridge/judge-import",
            "/api/bridge/judge-request",
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
