# Idea Vending Machine v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable, testable v0.1 that turns a raw idea into a deterministic Agent MD analysis and development-ready acceptance criteria.

**Architecture:** Keep domain analysis pure and framework-free, expose it through a minimal standard-library HTTP server, and render results in a single-page web UI. A single verification script runs tests and static safety checks; GitHub Actions calls the same entrypoint.

**Tech Stack:** Python 3.11+ standard library, HTML/CSS/JavaScript, unittest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-16-idea-vending-machine-design.md`

## Global Constraints
- No external runtime dependencies in v0.1.
- No SaaS, billing, authentication, or external LLM API in v0.1.
- NO GREEN WITHOUT EVIDENCE.
- Raw user input must never be inserted into HTML with `innerHTML`.
- `python scripts/verify.py` is the release-gate entrypoint.

---

### Task 1: Agent MD domain engine

**Files:**
- Create: `src/idea_vending/__init__.py`
- Create: `src/idea_vending/analyzer.py`
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Produces: `analyze_idea(idea: str) -> dict[str, object]`

- [ ] **Step 1: Write failing tests** for short-input rejection, deterministic output, and required result fields.
- [ ] **Step 2: Run** `python -m unittest tests.test_analyzer -v` and confirm failure because implementation does not exist.
- [ ] **Step 3: Implement** normalization, A0-A5 automation scoring, T1-T5 feasibility scoring, risks, MVP scope, and acceptance criteria.
- [ ] **Step 4: Re-run** the unit tests and require PASS.
- [ ] **Step 5: Commit** `feat: add deterministic Agent MD analyzer`.

### Task 2: HTTP API and minimal UI

**Files:**
- Create: `app.py`
- Create: `web/index.html`
- Create: `web/app.js`
- Create: `web/styles.css`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: `analyze_idea(idea: str)`
- Produces: GET `/`, POST `/api/analyze`

- [ ] **Step 1: Write failing HTTP tests** for index load, valid analysis request, malformed/short request.
- [ ] **Step 2: Run** `python -m unittest tests.test_http -v` and confirm RED.
- [ ] **Step 3: Implement** the minimal server with request-size limits and JSON-only API.
- [ ] **Step 4: Implement UI** using `textContent`/DOM nodes only for analysis output.
- [ ] **Step 5: Re-run** HTTP tests and require PASS.
- [ ] **Step 6: Commit** `feat: add idea vending web interface`.

### Task 3: Production Gate

**Files:**
- Create: `scripts/verify.py`
- Create: `.github/workflows/production-gate.yml`
- Create: `tests/test_security_contract.py`

**Interfaces:**
- Produces: `python scripts/verify.py` with exit code 0 only when all gates pass.

- [ ] **Step 1: Write failing contract test** that rejects `innerHTML` usage in `web/app.js` and verifies required files exist.
- [ ] **Step 2: Run** the test and confirm RED until verification assets exist.
- [ ] **Step 3: Implement** verification script to compile Python, run unittest discovery, and scan forbidden frontend sink usage.
- [ ] **Step 4: Add CI** that runs the same command on push and pull request.
- [ ] **Step 5: Run** `python scripts/verify.py` and require PASS.
- [ ] **Step 6: Commit** `ci: add evidence-based production gate`.

### Task 4: Operator documentation and final verification

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.gitignore`

**Interfaces:**
- Documents exact local run and verification commands.

- [ ] **Step 1: Write README** with purpose, run command, API example, and validation command.
- [ ] **Step 2: Write AGENTS.md** with raw-idea prohibition, acceptance-first, deterministic/AI separation, and NO GREEN WITHOUT EVIDENCE rules.
- [ ] **Step 3: Run** `python scripts/verify.py` from a clean working tree.
- [ ] **Step 4: Run** a smoke request against the local server and verify required fields.
- [ ] **Step 5: Commit** `docs: add operator and agent instructions`.
