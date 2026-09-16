from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SimpleBridgeUxTests(unittest.TestCase):
    def test_default_bridge_flow_exposes_only_three_user_actions(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        for expected in (
            'id="bridge-simple-flow"',
            'id="bridge-stage-label"',
            'id="bridge-chatgpt-continue"',
            'id="bridge-result-input"',
            'id="bridge-result-submit"',
            'id="bridge-advanced"',
            "ChatGPT에서 계속하기",
            "ChatGPT 결과 붙여넣기",
            ">계속<",
            ">분석 시작<",
        ):
            self.assertIn(expected, html)

        self.assertNotIn(">ChatGPT Plus로 분석<", html)

        advanced_at = html.index('id="bridge-advanced"')
        for technical_id in (
            'id="bridge-session"',
            'id="copy-forge-prompt"',
            'id="copy-forge-json"',
            'id="download-forge-json"',
            'id="forge-package"',
            'id="forge-result-file"',
            'id="copy-judge-prompt"',
            'id="copy-judge-json"',
            'id="download-judge-json"',
            'id="judge-package"',
            'id="judge-result-file"',
        ):
            self.assertGreater(html.index(technical_id), advanced_at, technical_id)

    def test_frontend_unifies_forge_and_judge_user_flow(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        for expected in (
            "function currentBridgePackage()",
            "function updateSimpleBridgeStage()",
            "async function copyTextWithFallback(",
            "function openChatGPTWithPrompt(",
            "#bridge-chatgpt-continue",
            "#bridge-result-input",
            "#bridge-result-submit",
            "https://chatgpt.com/",
            "document.execCommand('copy')",
        ):
            self.assertIn(expected, source)

        self.assertIn("currentJudgePackage ? 'judge' : 'forge'", source)
        self.assertIn("/api/bridge/forge-import", source)
        self.assertIn("/api/bridge/judge-import", source)
        self.assertIn("/api/bridge/judge-request", source)


if __name__ == "__main__":
    unittest.main()
