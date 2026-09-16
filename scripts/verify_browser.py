"""Deterministic real-Chromium verification for the E2B executive web flow."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import threading
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import Page, expect, sync_playwright
except ImportError as exc:
    raise SystemExit("FAIL: Playwright test dependency is required") from exc

from app import create_server
from src.idea_vending.evolution_runtime import run_evolution
from tests.test_evolution_runtime import (
    FakeEvaluationProvider,
    FakeIdeationProvider,
    FakeResearchProvider,
    NOW,
    TimeoutResearchProvider,
)

SCENARIOS = (
    "MODIFY",
    "GO",
    "HOLD",
    "KILL",
    "INCOMPLETE",
    "PROVIDER_NOT_CONFIGURED",
    "XSS",
)

IDEA_BASE = "고객 문의 반복업무를 예방 자동화하고 증거로 검증하는 운영 시스템"


def fail(message: str) -> None:
    raise AssertionError(message)


def build_completed(idea: str, scenario: str) -> dict:
    return run_evolution(
        idea,
        research_provider=FakeResearchProvider(),
        ideation_provider=FakeIdeationProvider(),
        evaluation_provider=FakeEvaluationProvider(scenario),
        now_provider=lambda: NOW,
    )


def fixture_runner(idea: str) -> dict:
    marker = idea.upper()
    if "INCOMPLETE" in marker:
        return run_evolution(
            idea,
            research_provider=TimeoutResearchProvider(),
            ideation_provider=FakeIdeationProvider(),
            evaluation_provider=FakeEvaluationProvider("go"),
            now_provider=lambda: NOW,
        )

    scenario = "go"
    for candidate in ("modify", "hold", "kill", "go"):
        if candidate.upper() in marker:
            scenario = candidate
            break
    result = build_completed(idea, scenario)

    if "XSS" in marker:
        safe_result = deepcopy(result)
        safe_result["state"]["executive_brief"]["thesis"] = idea
        safe_result["report"] = deepcopy(safe_result["state"]["executive_brief"])
        return safe_result
    return result


def start_server(
    *,
    runner: Callable[[str], dict] | None,
    environ: dict[str, str] | None = None,
):
    server = create_server(
        "127.0.0.1",
        0,
        evolve_runner=runner,
        environ={} if environ is None else environ,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, thread, base_url


def stop_server(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(2)


def submit(page: Page, base_url: str, idea: str) -> None:
    page.goto(base_url, wait_until="domcontentloaded")
    page.locator("#idea").fill(idea)
    page.get_by_role("button", name="아이디어 진화시키기").click()
    expect(page.locator("#evolve-submit")).to_be_enabled(timeout=20000)


def assert_completed_candidate_surface(page: Page, decision: str) -> None:
    expect(page.locator("#runtime-progress")).to_be_visible()
    expect(page.locator("#executive-decision")).to_be_visible()
    expect(page.locator("#decision-value")).to_have_text(decision)
    cards = page.locator(".candidate-card")
    expect(cards).to_have_count(10)
    families = cards.locator(".family-label").all_text_contents()
    if len(families) != 10 or len(set(families)) != 10:
        fail(f"expected ten unique candidate families, got {families}")
    first = cards.first
    first.locator("details.candidate-expand > summary").click()
    expect(first.locator(".dimension-list dt")).to_have_count(10)


def scenario_modify(page: Page, base_url: str) -> None:
    idea = f"MODIFY {IDEA_BASE}"
    submit(page, base_url, idea)
    assert_completed_candidate_surface(page, "MODIFY")
    expect(page.locator("#approve-direction")).to_be_enabled()
    page.locator("#approve-direction").click()
    expect(page.locator("#package")).to_be_visible()
    for selector in ("#spec-preview", "#design-preview", "#plan-preview"):
        expect(page.locator(selector)).not_to_be_empty()
    print("PASS: MODIFY")


def scenario_go(page: Page, base_url: str) -> None:
    idea = f"GO {IDEA_BASE} 원안 유지 검증"
    submit(page, base_url, idea)
    assert_completed_candidate_surface(page, "GO")
    page.locator("#approve-direction").click()
    expect(page.locator("#package")).to_be_visible()
    expect(page.locator("#spec-preview")).to_contain_text(idea)
    print("PASS: GO")


def scenario_hold(page: Page, base_url: str) -> None:
    submit(page, base_url, f"HOLD {IDEA_BASE}")
    expect(page.locator("#decision-value")).to_have_text("HOLD")
    expect(page.locator("#approve-direction")).to_be_disabled()
    expect(page.locator("#approval-guidance")).to_contain_text("HOLD")
    expect(page.locator("#package")).to_be_hidden()
    print("PASS: HOLD")


def scenario_kill(page: Page, base_url: str) -> None:
    submit(page, base_url, f"KILL {IDEA_BASE}")
    expect(page.locator("#decision-value")).to_have_text("KILL")
    expect(page.locator("#approve-direction")).to_be_disabled()
    expect(page.locator("#approval-guidance")).to_contain_text("KILL")
    expect(page.locator("#reasons-against li").first).to_be_visible()
    print("PASS: KILL")


def scenario_incomplete(page: Page, base_url: str) -> None:
    submit(page, base_url, f"INCOMPLETE {IDEA_BASE}")
    expect(page.locator("#runtime-progress")).to_be_visible()
    expect(page.locator("#runtime-failure")).to_be_visible()
    expect(page.locator("#executive-decision")).to_be_hidden()
    expect(page.locator("#approve-direction")).to_be_disabled()
    body = page.locator("body").inner_text()
    if "대표이사 판단" in body and page.locator("#executive-decision").is_visible():
        fail("incomplete runtime manufactured a visible business verdict")
    print("PASS: INCOMPLETE")


def scenario_provider_not_configured(page: Page, base_url: str) -> None:
    submit(page, base_url, f"PROVIDER_NOT_CONFIGURED {IDEA_BASE}")
    expect(page.locator("#status")).to_contain_text("Provider가 구성되지 않았습니다")
    expect(page.locator("#executive-decision")).to_be_hidden()
    body = page.locator("body").inner_text().lower()
    if "authorization:" in body or "bearer " in body:
        fail("provider-not-configured UI exposed credential-shaped material")
    print("PASS: PROVIDER_NOT_CONFIGURED")


def scenario_xss(page: Page, base_url: str) -> None:
    payload = '<img src=x onerror="window.__ivmXss=1">'
    idea = f"XSS {IDEA_BASE} {payload}"
    submit(page, base_url, idea)
    expect(page.locator("#decision-value")).to_have_text("GO")
    expect(page.locator("#decision-thesis")).to_have_text(idea)
    if page.locator('img[src="x"]').count() != 0:
        fail("untrusted idea text created an executable image element")
    executed = page.evaluate("typeof window.__ivmXss === 'undefined' ? null : window.__ivmXss")
    if executed is not None:
        fail("untrusted idea text executed JavaScript")
    print("PASS: XSS")


def main() -> None:
    fixture_server = fixture_thread = unconfigured_server = unconfigured_thread = None
    try:
        fixture_server, fixture_thread, fixture_url = start_server(runner=fixture_runner)
        unconfigured_server, unconfigured_thread, unconfigured_url = start_server(runner=None, environ={})
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                page = context.new_page()
                scenario_modify(page, fixture_url)
                scenario_go(page, fixture_url)
                scenario_hold(page, fixture_url)
                scenario_kill(page, fixture_url)
                scenario_incomplete(page, fixture_url)
                scenario_provider_not_configured(page, unconfigured_url)
                scenario_xss(page, fixture_url)
                context.close()
            finally:
                browser.close()
    except AssertionError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
    finally:
        if fixture_server is not None and fixture_thread is not None:
            stop_server(fixture_server, fixture_thread)
        if unconfigured_server is not None and unconfigured_thread is not None:
            stop_server(unconfigured_server, unconfigured_thread)
    print("BROWSER GREEN WITH EVIDENCE")


if __name__ == "__main__":
    main()
