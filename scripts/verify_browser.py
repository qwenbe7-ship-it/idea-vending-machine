"""Deterministic real-Chromium verification for autonomous v0.4 and Bridge fallback."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:
    raise SystemExit("FAIL: Playwright test dependency is required") from exc

from app import create_server as create_bridge_server
from src.idea_vending.bridge_contract import BRIDGE_VERSION
from tests.test_bridge_forge import valid_forge_result
from tests.test_evolution_runtime import FakeEvaluationProvider
from tests.test_evolve_api import completed_result
from v04_app import create_server as create_autonomous_server

SCENARIOS = (
    "BRIDGE_SIMPLE_UX",
    "BRIDGE_FORGE_EXPORT",
    "BRIDGE_INTENT_CONTEXT",
    "BRIDGE_FORGE_IMPORT",
    "BRIDGE_LOCAL_VALIDATION_SUCCESS",
    "BRIDGE_LOCAL_VALIDATION_ERROR",
    "BRIDGE_PACKAGE_PASTE_REJECTED",
    "BRIDGE_JUDGE_EXPORT",
    "BRIDGE_JUDGE_IMPORT",
    "BRIDGE_GO_APPROVAL",
    "BRIDGE_MODIFY_APPROVAL",
    "BRIDGE_HOLD_BLOCKED",
    "BRIDGE_KILL_BLOCKED",
    "BRIDGE_MALFORMED_IMPORT",
    "BRIDGE_WRONG_SESSION",
    "BRIDGE_REPLAY",
    "BRIDGE_XSS",
    "BRIDGE_READY_WITHOUT_API",
    "AUTO_ONE_CLICK_COMPLETE",
    "AUTO_SUMMARY_TRUSTED",
    "AUTO_GO_APPROVAL",
    "AUTO_HOLD_BLOCKED",
    "AUTO_PROVIDER_NOT_CONFIGURED_FALLBACK",
    "AUTO_STALE_BRIDGE_INVALIDATED",
)

IDEA_BASE = "고객 문의 반복업무를 예방 자동화하고 증거로 검증하는 운영 시스템"
FORGE_RESULT_SECTIONS = {
    "landscape_research",
    "extract_assumptions",
    "challenge_assumptions",
    "propose_reframes",
    "discover_mechanisms",
    "forge_candidates",
    "collision_research",
}
RESEARCH_PLAN_CATEGORIES = {
    "market_customer_demand",
    "workflow_economics",
    "alternatives_incumbents",
    "implementation_feasibility",
    "data_quality",
    "regulation_security",
    "failure_blockers",
    "adjacent_mechanisms",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def _serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base_url


def start_bridge_server():
    return _serve(create_bridge_server("127.0.0.1", 0, environ={}))


def start_autonomous_server(scenario: str | None, *, poison_summary: bool = False):
    runner = None
    if scenario is not None:
        def runner(idea: str) -> dict:
            result = completed_result(idea, scenario)
            if poison_summary:
                result["automation_summary"] = {
                    "mode": "untrusted",
                    "candidate_count": 999,
                    "decision": "KILL",
                }
            return result
    return _serve(create_autonomous_server("127.0.0.1", 0, evolve_runner=runner, environ={}))


def stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(2)


def hidden_json(page: Page, selector: str) -> dict:
    raw = page.locator(selector).text_content() or ""
    return json.loads(raw)


def start_bridge(page: Page, base_url: str, idea: str) -> dict:
    page.goto(base_url, wait_until="domcontentloaded")
    page.locator("#idea").fill(idea)
    page.get_by_role("button", name="ChatGPT Plus로 분석").click()
    expect(page.locator("#bridge-workflow")).to_be_visible(timeout=20000)
    expect(page.locator("#evolve-submit")).to_be_enabled()
    expect(page.locator("#copy-forge-prompt")).to_be_visible()
    expect(page.locator("#copy-forge-prompt")).to_have_text("ChatGPT에서 계속하기")
    expect(page.locator("#forge-result-input")).to_be_visible()
    expect(page.locator("#import-forge-result")).to_contain_text("결과 검증")
    expect(page.locator("#copy-forge-json")).to_be_hidden()
    package = hidden_json(page, "#forge-package")
    if package.get("request_type") != "forge" or package.get("bridge_version") != BRIDGE_VERSION:
        fail("Forge package contract was not rendered")
    return package


def import_forge(page: Page, result: dict | None = None) -> dict:
    payload = valid_forge_result() if result is None else result
    page.locator("#forge-result-input").fill(json.dumps(payload, ensure_ascii=False))
    page.locator("#import-forge-result").click()
    expect(page.locator("#judge-step")).to_be_visible(timeout=20000)
    expect(page.locator("#forge-state")).to_contain_text("완료")
    expect(page.locator("#forge-validation-status")).to_be_visible()
    expect(page.locator("#forge-validation-status")).to_contain_text("검증 완료 · 10개 후보")
    expect(page.locator("#copy-judge-prompt")).to_have_text("ChatGPT에서 계속하기")
    expect(page.locator("#judge-result-input")).to_be_visible()
    expect(page.locator("#import-judge-result")).to_contain_text("최종 검증")
    package = hidden_json(page, "#judge-package")
    if package.get("request_type") != "judge" or len(package.get("candidates", [])) != 10:
        fail("Judge package contract was not rendered")
    return package


def make_judge_result(judge_package: dict, scenario: str) -> dict:
    provider = FakeEvaluationProvider(scenario)
    raw = provider.evaluate(
        {
            "evidence_graph": {"records": judge_package["evidence"]},
            "baseline": judge_package["baseline"],
            "candidates": judge_package["candidates"],
        }
    )
    return {"critiques": raw["critiques"], "additional_evidence": []}


def import_judge(page: Page, judge_package: dict, scenario: str) -> None:
    payload = make_judge_result(judge_package, scenario)
    page.locator("#judge-result-input").fill(json.dumps(payload, ensure_ascii=False))
    page.locator("#import-judge-result").click()
    expect(page.locator("#executive-decision")).to_be_visible(timeout=20000)
    expect(page.locator("#candidate-grid .candidate-card")).to_have_count(10)
    expect(page.locator("#judge-state")).to_contain_text("공식 판단 생성")
    expect(page.locator("#judge-validation-status")).to_be_visible()
    expect(page.locator("#judge-validation-status")).to_contain_text("검증 완료")


def validate_browser_forge_intent_context(forge_package: dict, idea: str) -> None:
    context = forge_package.get("intent_context")
    if not isinstance(context, dict):
        fail("browser Forge package did not expose intent_context")
    intent = context.get("intent_model")
    plan = context.get("research_plan")
    if not isinstance(intent, dict) or intent.get("primary_objective") != idea:
        fail("browser Forge package did not preserve the exact primary objective")
    if intent.get("primary_buyer") is not None:
        fail("browser Forge package invented an unknown primary buyer")
    unknowns = intent.get("material_unknowns")
    if not isinstance(unknowns, list) or "primary_buyer" not in unknowns or "success_metrics" not in unknowns:
        fail("browser Forge package did not preserve material intent unknowns")
    questions = plan.get("research_questions") if isinstance(plan, dict) else None
    if not isinstance(questions, dict) or set(questions) != RESEARCH_PLAN_CATEGORIES:
        fail("browser Forge package research plan did not contain the eight bounded categories")
    if any(not isinstance(items, list) or not items for items in questions.values()):
        fail("browser Forge package research plan contained an empty question category")
    contract = forge_package.get("result_contract")
    if not isinstance(contract, dict):
        fail("browser Forge package result_contract was missing")
    required = contract.get("required_top_level_keys")
    schemas = contract.get("section_schemas")
    if (
        not isinstance(required, list)
        or len(required) != 7
        or set(required) != FORGE_RESULT_SECTIONS
        or not isinstance(schemas, dict)
        or set(schemas) != FORGE_RESULT_SECTIONS
    ):
        fail("intent-aware browser Forge package changed the seven-section result authority")
    instruction = forge_package.get("chatgpt_instruction")
    if not isinstance(instruction, str) or idea not in instruction or "intent_context.research_plan" not in instruction:
        fail("browser Forge instruction was not driven by the supplied intent context")


def scenario_go_round_trip(page: Page, base_url: str) -> None:
    idea = f"GO {IDEA_BASE} 원안 유지 검증"
    forge_package = start_bridge(page, base_url, idea)
    print("PASS: BRIDGE_SIMPLE_UX")
    expect(page.locator("#forge-package")).to_contain_text('"candidate_count": 10')
    validate_browser_forge_intent_context(forge_package, idea)
    print("PASS: BRIDGE_INTENT_CONTEXT")
    page.locator("#copy-forge-prompt").click()
    expect(page.locator("#status")).to_contain_text("복사했습니다")
    copied = page.evaluate("navigator.clipboard.readText()")
    if "PACKAGE JSON:" not in copied or forge_package["bridge_session_id"] not in copied:
        fail("Forge prompt copy did not contain the trusted export package")
    print("PASS: BRIDGE_FORGE_EXPORT")

    judge_package = import_forge(page)
    print("PASS: BRIDGE_FORGE_IMPORT")
    print("PASS: BRIDGE_LOCAL_VALIDATION_SUCCESS")
    expect(page.locator("#judge-step")).to_contain_text("별도의 새 ChatGPT 대화")
    print("PASS: BRIDGE_JUDGE_EXPORT")

    page.locator("#import-forge-result").click()
    expect(page.locator("#judge-step")).to_be_visible(timeout=20000)
    expect(page.locator("#status")).to_contain_text("2/2")
    print("PASS: BRIDGE_REPLAY")

    import_judge(page, judge_package, "go")
    expect(page.locator("#decision-value")).to_have_text("GO")
    print("PASS: BRIDGE_JUDGE_IMPORT")

    page.locator("#approve-direction").click()
    expect(page.locator("#package")).to_be_visible(timeout=20000)
    for selector in ("#spec-preview", "#design-preview", "#plan-preview"):
        expect(page.locator(selector)).not_to_be_empty()
    print("PASS: BRIDGE_GO_APPROVAL")


def scenario_modify(page: Page, base_url: str) -> None:
    start_bridge(page, base_url, f"MODIFY {IDEA_BASE}")
    judge = import_forge(page)
    import_judge(page, judge, "modify")
    expect(page.locator("#decision-value")).to_have_text("MODIFY")
    expect(page.locator("#approve-direction")).to_be_enabled()
    page.locator("#approve-direction").click()
    expect(page.locator("#package")).to_be_visible(timeout=20000)
    expect(page.locator("#spec-preview")).not_to_be_empty()
    print("PASS: BRIDGE_MODIFY_APPROVAL")


def scenario_hold(page: Page, base_url: str) -> None:
    start_bridge(page, base_url, f"HOLD {IDEA_BASE}")
    judge = import_forge(page)
    import_judge(page, judge, "hold")
    expect(page.locator("#decision-value")).to_have_text("HOLD")
    expect(page.locator("#approve-direction")).to_be_disabled()
    expect(page.locator("#approval-guidance")).to_contain_text("HOLD")
    expect(page.locator("#package")).to_be_hidden()
    print("PASS: BRIDGE_HOLD_BLOCKED")


def scenario_kill(page: Page, base_url: str) -> None:
    start_bridge(page, base_url, f"KILL {IDEA_BASE}")
    judge = import_forge(page)
    import_judge(page, judge, "kill")
    expect(page.locator("#decision-value")).to_have_text("KILL")
    expect(page.locator("#approve-direction")).to_be_disabled()
    expect(page.locator("#approval-guidance")).to_contain_text("KILL")
    expect(page.locator("#package")).to_be_hidden()
    print("PASS: BRIDGE_KILL_BLOCKED")


def scenario_local_validation_error(page: Page, base_url: str) -> None:
    start_bridge(page, base_url, f"LOCAL ERROR {IDEA_BASE}")
    invalid = valid_forge_result()
    invalid["landscape_research"][0]["publication_date"] = "date unavailable"
    page.locator("#forge-result-input").fill(json.dumps(invalid, ensure_ascii=False))
    page.locator("#import-forge-result").click()
    local = page.locator("#forge-validation-status")
    expect(local).to_be_visible(timeout=20000)
    expect(local).to_have_attribute("data-state", "error")
    expect(local).to_contain_text("YYYY-MM-DD")
    expect(page.locator("#judge-step")).to_be_hidden()
    print("PASS: BRIDGE_LOCAL_VALIDATION_ERROR")


def scenario_package_paste_rejected(page: Page, base_url: str) -> None:
    forge_package = start_bridge(page, base_url, f"PACKAGE PASTE {IDEA_BASE}")
    page.locator("#forge-result-input").fill(json.dumps(forge_package, ensure_ascii=False))
    page.locator("#import-forge-result").click()
    local = page.locator("#forge-validation-status")
    expect(local).to_be_visible(timeout=20000)
    expect(local).to_have_attribute("data-state", "error")
    expect(local).to_contain_text("실행용 Forge 패키지")
    expect(local).to_contain_text("최종")
    expect(page.locator("#judge-step")).to_be_hidden()
    print("PASS: BRIDGE_PACKAGE_PASTE_REJECTED")


def scenario_malformed_import(page: Page, base_url: str) -> None:
    start_bridge(page, base_url, f"MALFORMED {IDEA_BASE}")
    page.locator("#forge-result-input").fill("{}")
    page.locator("#import-forge-result").click()
    expect(page.locator("#status")).to_contain_text("bridge_import_invalid", timeout=20000)
    expect(page.locator("#judge-step")).to_be_hidden()
    print("PASS: BRIDGE_MALFORMED_IMPORT")


def scenario_wrong_session(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    response = page.evaluate(
        """async ({version, result}) => {
          const response = await fetch('/api/bridge/forge-import', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              bridge_session_id: 'br_abcdefghijklmnop',
              bridge_version: version,
              result,
            }),
          });
          return {status: response.status, body: await response.json()};
        }""",
        {"version": BRIDGE_VERSION, "result": valid_forge_result()},
    )
    if response["status"] != 404 or response["body"].get("error") != "bridge_session_not_found_or_expired":
        fail(f"wrong-session import did not fail closed: {response}")
    print("PASS: BRIDGE_WRONG_SESSION")


def scenario_xss(page: Page, base_url: str) -> None:
    payload = '<img src=x onerror="window.__ivmBridgeXss=1">'
    idea = f"XSS {IDEA_BASE} {payload}"
    forge_package = start_bridge(page, base_url, idea)
    if forge_package.get("raw_idea") != idea:
        fail("untrusted bridge idea was not preserved after safe JSON decoding")
    if page.locator('img[src="x"]').count() != 0:
        fail("untrusted bridge idea created an executable image element")
    executed = page.evaluate("typeof window.__ivmBridgeXss === 'undefined' ? null : window.__ivmBridgeXss")
    if executed is not None:
        fail("untrusted bridge idea executed JavaScript")
    print("PASS: BRIDGE_XSS")


def scenario_ready_without_api(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    ready = page.evaluate("async () => (await fetch('/readyz')).json()")
    if ready.get("status") != "ready":
        fail(f"Bridge readiness was not ready: {ready}")
    if ready.get("default_mode") != "chatgpt_plus_bridge":
        fail(f"Bridge was not the default mode: {ready}")
    if ready.get("modes", {}).get("openai_api") != "not_configured":
        fail(f"API mode unexpectedly configured in browser gate: {ready}")
    expect(page.locator(".primary-mode")).to_contain_text("ChatGPT Plus Bridge")
    expect(page.locator("#api-mode-indicator")).to_be_hidden()
    print("PASS: BRIDGE_READY_WITHOUT_API")


def scenario_auto_go(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="자동 분석 시작")).to_be_visible(timeout=20000)
    expect(page.locator("#autonomous-workflow")).to_be_visible()
    expect(page.locator("#autonomous-workflow")).to_contain_text("시장 조사")
    expect(page.locator("#autonomous-workflow")).to_contain_text("반증 탐색")
    expect(page.locator("#autonomous-workflow")).to_contain_text("10개 대안")
    expect(page.locator("#autonomous-workflow")).to_contain_text("독립 심사")
    expect(page.locator("#autonomous-workflow")).to_contain_text("최종 결정")
    expect(page.locator("#bridge-workflow")).to_be_hidden()

    page.locator("#idea").fill(f"AUTO GO {IDEA_BASE}")
    page.get_by_role("button", name="자동 분석 시작").click()
    expect(page.locator("#executive-decision")).to_be_visible(timeout=20000)
    expect(page.locator("#candidate-grid .candidate-card")).to_have_count(10)
    expect(page.locator("#automation-summary")).to_be_visible()
    expect(page.locator("#automation-candidate-count")).to_have_text("10")
    expect(page.locator("#automation-decision")).to_have_text("GO")
    expect(page.locator("#bridge-workflow")).to_be_hidden()
    print("PASS: AUTO_ONE_CLICK_COMPLETE")

    evidence_text = page.locator("#automation-evidence-count").inner_text().strip()
    critique_text = page.locator("#automation-critique-count").inner_text().strip()
    if not evidence_text.isdigit() or int(evidence_text) <= 0:
        fail(f"autonomous summary did not report trusted evidence count: {evidence_text!r}")
    if critique_text != "11":
        fail(f"autonomous summary did not report baseline + 10 independent critiques: {critique_text!r}")
    if page.locator("#automation-candidate-count").inner_text().strip() == "999":
        fail("provider-supplied automation summary was trusted")
    print("PASS: AUTO_SUMMARY_TRUSTED")

    expect(page.locator("#approve-direction")).to_be_enabled()
    page.locator("#approve-direction").click()
    expect(page.locator("#package")).to_be_visible(timeout=20000)
    for selector in ("#spec-preview", "#design-preview", "#plan-preview"):
        expect(page.locator(selector)).not_to_be_empty()
    print("PASS: AUTO_GO_APPROVAL")


def scenario_auto_hold(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    page.locator("#idea").fill(f"AUTO HOLD {IDEA_BASE}")
    page.get_by_role("button", name="자동 분석 시작").click()
    expect(page.locator("#executive-decision")).to_be_visible(timeout=20000)
    expect(page.locator("#decision-value")).to_have_text("HOLD")
    expect(page.locator("#candidate-grid .candidate-card")).to_have_count(10)
    expect(page.locator("#approve-direction")).to_be_disabled()
    expect(page.locator("#package")).to_be_hidden()
    print("PASS: AUTO_HOLD_BLOCKED")


def scenario_auto_unconfigured_fallback(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="자동 분석 시작")).to_be_visible(timeout=20000)
    page.locator("#idea").fill(f"AUTO FALLBACK {IDEA_BASE}")
    page.get_by_role("button", name="자동 분석 시작").click()
    expect(page.locator("#status")).to_contain_text(
        "자동 분석 엔진이 아직 설정되지 않았습니다.", timeout=20000
    )
    fallback_open = page.locator("#bridge-fallback").evaluate("node => node.open")
    if fallback_open is not True:
        fail("Bridge fallback disclosure was not opened after missing autonomous provider")
    page.locator("#enable-bridge-fallback").click()
    expect(page.locator("#evolve-submit")).to_have_attribute("aria-label", "ChatGPT Plus로 분석")
    page.locator("#evolve-submit").click()
    expect(page.locator("#bridge-workflow")).to_be_visible(timeout=20000)
    print("PASS: AUTO_PROVIDER_NOT_CONFIGURED_FALLBACK")


def scenario_auto_stale_bridge_invalidated(page: Page, base_url: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    old_idea = f"OLD {IDEA_BASE}"
    new_idea = f"NEW {IDEA_BASE}"

    page.locator("#idea").fill(old_idea)
    page.get_by_role("button", name="자동 분석 시작").click()
    expect(page.locator("#status")).to_contain_text(
        "자동 분석 엔진이 아직 설정되지 않았습니다.", timeout=20000
    )
    page.locator("#enable-bridge-fallback").click()
    expect(page.locator("#bridge-workflow")).to_be_hidden()
    expect(page.locator("#evolve-submit")).to_have_text("Bridge로 분석 시작")
    page.locator("#evolve-submit").click()
    expect(page.locator("#bridge-workflow")).to_be_visible(timeout=20000)
    old_package = hidden_json(page, "#forge-package")
    if old_package.get("raw_idea") != old_idea:
        fail("initial fallback Forge package did not match the submitted idea")

    page.locator("#idea").fill(new_idea)
    expect(page.locator("#bridge-workflow")).to_be_hidden()
    expect(page.locator("#status")).to_contain_text("아이디어가 변경되었습니다")
    page.locator("#evolve-submit").click()
    expect(page.locator("#bridge-workflow")).to_be_visible(timeout=20000)
    new_package = hidden_json(page, "#forge-package")
    if new_package.get("raw_idea") != new_idea:
        fail("new fallback Forge package reused a stale raw_idea")
    if new_package.get("bridge_session_id") == old_package.get("bridge_session_id"):
        fail("new fallback Forge package reused a stale bridge session")
    print("PASS: AUTO_STALE_BRIDGE_INVALIDATED")


def run_bridge_suite(browser) -> None:
    server = thread = None
    try:
        server, thread, base_url = start_bridge_server()
        context = browser.new_context()
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url)
        page = context.new_page()
        scenario_go_round_trip(page, base_url)
        scenario_modify(page, base_url)
        scenario_hold(page, base_url)
        scenario_kill(page, base_url)
        scenario_local_validation_error(page, base_url)
        scenario_package_paste_rejected(page, base_url)
        scenario_malformed_import(page, base_url)
        scenario_wrong_session(page, base_url)
        scenario_xss(page, base_url)
        scenario_ready_without_api(page, base_url)
        context.close()
    finally:
        if server is not None and thread is not None:
            stop_server(server, thread)


def run_autonomous_suite(browser) -> None:
    for scenario, callback, poison_summary in (
        ("go", scenario_auto_go, True),
        ("hold", scenario_auto_hold, False),
        (None, scenario_auto_unconfigured_fallback, False),
        (None, scenario_auto_stale_bridge_invalidated, False),
    ):
        server = thread = None
        try:
            server, thread, base_url = start_autonomous_server(scenario, poison_summary=poison_summary)
            context = browser.new_context()
            page = context.new_page()
            callback(page, base_url)
            context.close()
        finally:
            if server is not None and thread is not None:
                stop_server(server, thread)


def main() -> None:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                run_bridge_suite(browser)
                run_autonomous_suite(browser)
            finally:
                browser.close()
    except AssertionError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    print("BROWSER GREEN WITH EVIDENCE")


if __name__ == "__main__":
    main()
