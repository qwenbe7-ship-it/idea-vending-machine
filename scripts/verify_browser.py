"""Deterministic real-Chromium verification for ChatGPT Plus Bridge Mode."""

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

from app import create_server
from src.idea_vending.bridge_contract import BRIDGE_VERSION
from tests.test_bridge_forge import valid_forge_result
from tests.test_evolution_runtime import FakeEvaluationProvider

SCENARIOS = (
    "BRIDGE_FORGE_EXPORT",
    "BRIDGE_FORGE_IMPORT",
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
)

IDEA_BASE = "고객 문의 반복업무를 예방 자동화하고 증거로 검증하는 운영 시스템"


def fail(message: str) -> None:
    raise AssertionError(message)


def start_server():
    server = create_server("127.0.0.1", 0, environ={})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base_url


def stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(2)


def start_bridge(page: Page, base_url: str, idea: str) -> dict:
    page.goto(base_url, wait_until="domcontentloaded")
    page.locator("#idea").fill(idea)
    page.get_by_role("button", name="ChatGPT Plus로 분석").click()
    expect(page.locator("#bridge-workflow")).to_be_visible(timeout=20000)
    expect(page.locator("#evolve-submit")).to_be_enabled()
    package = json.loads(page.locator("#forge-package").inner_text())
    if package.get("request_type") != "forge" or package.get("bridge_version") != BRIDGE_VERSION:
        fail("Forge package contract was not rendered")
    return package


def import_forge(page: Page, result: dict | None = None) -> dict:
    payload = valid_forge_result() if result is None else result
    page.locator("#forge-result-input").fill(json.dumps(payload, ensure_ascii=False))
    page.locator("#import-forge-result").click()
    expect(page.locator("#judge-step")).to_be_visible(timeout=20000)
    expect(page.locator("#forge-state")).to_contain_text("검증 완료")
    package = json.loads(page.locator("#judge-package").inner_text())
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


def scenario_go_round_trip(page: Page, base_url: str) -> None:
    forge_package = start_bridge(page, base_url, f"GO {IDEA_BASE} 원안 유지 검증")
    expect(page.locator("#forge-package")).to_contain_text('"candidate_count": 10')
    page.locator("#copy-forge-prompt").click()
    expect(page.locator("#status")).to_contain_text("복사했습니다")
    copied = page.evaluate("navigator.clipboard.readText()")
    if "PACKAGE JSON:" not in copied or forge_package["bridge_session_id"] not in copied:
        fail("Forge prompt copy did not contain the trusted export package")
    print("PASS: BRIDGE_FORGE_EXPORT")

    judge_package = import_forge(page)
    print("PASS: BRIDGE_FORGE_IMPORT")
    expect(page.locator("#judge-step")).to_contain_text("별도의 새 ChatGPT 대화")
    print("PASS: BRIDGE_JUDGE_EXPORT")

    # Same Forge result replay must remain idempotent even after Judge was requested.
    page.locator("#import-forge-result").click()
    expect(page.locator("#judge-step")).to_be_visible(timeout=20000)
    expect(page.locator("#status")).to_contain_text("2단계")
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
    start_bridge(page, base_url, idea)
    expect(page.locator("#forge-package")).to_contain_text(payload)
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


def main() -> None:
    server = thread = None
    try:
        server, thread, base_url = start_server()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base_url)
                page = context.new_page()
                scenario_go_round_trip(page, base_url)
                scenario_modify(page, base_url)
                scenario_hold(page, base_url)
                scenario_kill(page, base_url)
                scenario_malformed_import(page, base_url)
                scenario_wrong_session(page, base_url)
                scenario_xss(page, base_url)
                scenario_ready_without_api(page, base_url)
                context.close()
            finally:
                browser.close()
    except AssertionError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    finally:
        if server is not None and thread is not None:
            stop_server(server, thread)
    print("BROWSER GREEN WITH EVIDENCE")


if __name__ == "__main__":
    main()
