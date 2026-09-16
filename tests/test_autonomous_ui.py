from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AutonomousUITests(unittest.TestCase):
    def test_v04_server_injects_autonomous_ui_layer_without_replacing_legacy_assets(self):
        source = (ROOT / "v04_app.py").read_text(encoding="utf-8")
        self.assertIn('"/v04.js"', source)
        self.assertIn('web/v04.js', source.replace('\\\\', '/'))
        self.assertIn('AUTONOMOUS_UI_SCRIPT', source)

    def test_primary_ui_is_one_click_autonomous_and_bridge_is_fallback(self):
        source = (ROOT / "web" / "v04.js").read_text(encoding="utf-8")
        for expected in (
            "자동 분석 시작",
            "AUTONOMOUS DUE DILIGENCE",
            "시장 조사",
            "반증 탐색",
            "10개 대안",
            "독립 심사",
            "최종 결정",
            "postJson('/api/evolve', {idea: ideaInput.value})",
            "renderEvolutionResult(result)",
            "automation_summary",
            "고급 옵션 · ChatGPT Plus Bridge 사용",
            "provider_not_configured",
            "자동 분석 엔진이 아직 설정되지 않았습니다.",
        ):
            self.assertIn(expected, source)

        self.assertNotIn("innerHTML", source)
        self.assertNotIn("document.write(", source)
        self.assertNotIn("eval(", source)

    def test_fallback_requires_explicit_user_choice_before_legacy_bridge_submit(self):
        source = (ROOT / "web" / "v04.js").read_text(encoding="utf-8")
        self.assertIn("bridgeFallbackEnabled", source)
        self.assertIn("enable-bridge-fallback", source)
        self.assertIn("event.stopImmediatePropagation()", source)
        self.assertIn("if (bridgeFallbackEnabled)", source)


if __name__ == "__main__":
    unittest.main()
