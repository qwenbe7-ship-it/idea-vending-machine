from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebContractTests(unittest.TestCase):
    def test_plus_bridge_is_primary_executive_flow(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for expected in (
            'id="evolve-submit"',
            'id="bridge-workflow"',
            'id="bridge-session"',
            'id="forge-package"',
            'id="copy-forge-prompt"',
            'id="copy-forge-json"',
            'id="download-forge-json"',
            'id="forge-result-input"',
            'id="forge-result-file"',
            'id="import-forge-result"',
            'id="forge-validation-status"',
            'id="judge-package"',
            'id="copy-judge-prompt"',
            'id="copy-judge-json"',
            'id="download-judge-json"',
            'id="judge-result-input"',
            'id="judge-result-file"',
            'id="import-judge-result"',
            'id="judge-validation-status"',
            'id="api-mode-indicator"',
            'id="runtime-progress"',
            'id="executive-decision"',
            'id="candidate-grid"',
            'id="evidence-report"',
            'id="detailed-report"',
            'id="approve-direction"',
            'id="package"',
            'id="spec-preview"',
            'id="design-preview"',
            'id="plan-preview"',
        ):
            self.assertIn(expected, html)
        self.assertIn('src="/bridge_validation.js"', html)
        self.assertIn("ChatGPT Plus로 분석", html)
        self.assertIn("별도의 새 ChatGPT 대화", html)

    def test_frontend_uses_bridge_endpoints_and_server_owned_approval(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for path in (
            "/readyz",
            "/api/bridge/forge-request",
            "/api/bridge/forge-import",
            "/api/bridge/judge-request",
            "/api/bridge/judge-import",
            "/api/evolve/approve",
        ):
            self.assertIn(path, source)
        self.assertIn("{runtime_id: currentRuntimeId}", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, decision", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, confidence", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, selected", source)
        self.assertNotIn("{runtime_id: currentRuntimeId, human_decision", source)

    def test_frontend_uses_safe_dom_json_files_and_clipboard(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for forbidden in (
            "innerHTML",
            "outerHTML",
            "document.write(",
            "eval(",
            "exec(",
            "OPENAI_API_KEY",
            "sk-",
            "api_key",
            "provider_url",
            "system_prompt",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("textContent", source)
        self.assertIn("replaceChildren", source)
        self.assertIn("navigator.clipboard", source)
        self.assertIn("file.text()", source)
        self.assertIn("application/json", source)
        self.assertIn("new Blob", source)
        self.assertIn("URL.createObjectURL", source)
        self.assertIn("noopener noreferrer", source)

    def test_bridge_browser_wraps_only_server_session_and_version_around_results(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        match = re.search(
            r"function makeBridgeEnvelope\(result\) \{(?P<body>.*?)\n\}",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("bridge_session_id: currentBridgeSessionId", body)
        self.assertIn("bridge_version: currentBridgeVersion", body)
        self.assertIn("result", body)
        for forbidden in ("decision", "confidence", "human_decision", "selected_concept_id"):
            self.assertNotIn(forbidden, body)

    def test_bridge_imports_render_local_server_validation_status(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "web" / "bridge_validation.js").read_text(encoding="utf-8")
        self.assertIn('id="forge-validation-status"', html)
        self.assertIn('id="judge-validation-status"', html)
        self.assertIn("function renderBridgeValidation", source)
        self.assertIn("#forge-validation-status", source)
        self.assertIn("#judge-validation-status", source)
        self.assertIn("validation_error", source)
        self.assertIn("repair_instruction", source)
        self.assertIn("검증 중", source)
        self.assertIn("검증 완료 · 10개 후보", source)
        for forbidden in ("innerHTML", "outerHTML", "document.write(", "eval(", "new Function("):
            self.assertNotIn(forbidden, source)

    def test_changed_idea_invalidates_stale_bridge_before_new_fallback_run(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        autonomous = (ROOT / "web" / "v04.js").read_text(encoding="utf-8")
        self.assertIn("ideaInput.addEventListener('input'", source)
        self.assertIn("currentForgePackage.raw_idea", source)
        self.assertIn("resetBridge()", source)
        self.assertIn("resetBridge()", autonomous)
        self.assertIn("새 분석을 시작", source)

    def test_forge_ui_distinguishes_execution_package_from_returned_result(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("① ChatGPT에서 Forge 실행", html)
        self.assertIn("② ChatGPT가 생성한 최종 JSON만 붙여넣기", html)
        self.assertIn("실행용 패키지 JSON을 이 칸에 붙이지 마세요", html)
        self.assertIn("③ 결과 검증하고 계속", html)

    def test_runtime_failure_guidance_distinguishes_groq_auth_and_permission(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("provider_auth_failed", source)
        self.assertIn("Groq API 인증에 실패", source)
        self.assertIn("provider_permission_denied", source)
        self.assertIn("openai/gpt-oss-120b", source)
        self.assertIn("provider_rate_limited", source)

    def test_runtime_and_reality_evaluation_are_rendered_from_server_payload(self):
        source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for expected in (
            "stage_events",
            "candidate_reality_assessments",
            "dimension_statuses",
            "hard_or_material_blockers",
            "material_unknowns",
            "evidence_graph",
            "detailed_analysis",
        ):
            self.assertIn(expected, source)


if __name__ == "__main__":
    unittest.main()
