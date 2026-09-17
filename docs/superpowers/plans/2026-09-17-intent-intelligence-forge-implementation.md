# Intent Intelligence Forge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn short natural-language ideas into explicit intent models, intent-driven research, traceable Forge outputs, independent Judge critiques, and deterministic final decisions with no hidden Bridge contract rules.

**Architecture:** Add an explicit Intent Model and research-plan stage ahead of the existing Forge phases, then unify Bridge schema generation and server validation around a canonical Python contract. Preserve the current trust boundary: ChatGPT supplies untrusted research/generation, while the server owns IDs, validation, replay, official decisions, and human approval. Validation failures become structured local UI errors rather than invisible global status changes.

**Tech Stack:** Python 3 standard library runtime, existing Idea Vending Machine contracts/runtime, vanilla JavaScript/HTML frontend, unittest/Playwright browser verification, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-17-intent-intelligence-forge-design.md`

## Global Constraints

- Keep ChatGPT/LLM output untrusted until server validation and replay succeed.
- Keep official `GO/MODIFY/HOLD/KILL`, confidence, selected concept, and human approval server-owned.
- Do not duplicate semantic validation rules in browser JavaScript.
- Preserve exactly ten canonical candidate families.
- Do not silently fabricate missing user facts; unresolved items remain explicit unknowns.
- `publication_date` admitted into trusted evidence must be an ISO calendar date `YYYY-MM-DD`.
- Earlier Forge phases may reference only evidence already available at that phase; collision evidence cannot be forward-referenced.
- All production behavior changes must begin with a failing regression test and end with full regression and real-browser verification.

---

### Task 1: Canonical Bridge contract and hidden-rule elimination

**Files:**
- Create: `src/idea_vending/bridge_schema.py`
- Modify: `src/idea_vending/bridge_request.py`
- Modify: `src/idea_vending/bridge_replay.py`
- Modify: `src/idea_vending/evidence_graph.py` only if shared helpers are required without weakening validation
- Test: `tests/test_bridge_prompt_contract.py`
- Test: `tests/test_bridge_forge.py`

**Interfaces:**
- Produces: `evidence_draft_schema() -> dict[str, Any]`
- Produces: `validate_bridge_evidence_draft(draft: Any, *, allowed_claim_refs: set[str] | None = None) -> None`
- Consumes: existing evidence enums and candidate-family constants

- [ ] **Step 1: Write failing contract tests**

Add tests asserting that the exported Forge schema communicates the actual server constraints:

```python
def test_forge_package_exposes_iso_publication_date_contract():
    package = create_forge_package(IDEA, SESSION_ID, NOW)
    publication_date = (
        package["result_contract"]["section_schemas"]["landscape_research"]
        ["items"]["properties"]["publication_date"]
    )
    self.assertEqual(publication_date["type"], "string")
    self.assertEqual(publication_date["pattern"], r"^\\d{4}-\\d{2}-\\d{2}$")


def test_forge_instruction_forbids_forward_collision_claim_references():
    package = create_forge_package(IDEA, SESSION_ID, NOW)
    instruction = package["chatgpt_instruction"]
    self.assertIn("collision evidence cannot be referenced", instruction)
    self.assertIn("landscape_research", instruction)
```

Add a Forge import regression test proving a candidate that references a `bc_` created only in `collision_research` is rejected with the precise internal validation code.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python -m unittest tests.test_bridge_prompt_contract tests.test_bridge_forge -v
```

Expected: the new schema/instruction assertions fail on current behavior.

- [ ] **Step 3: Implement `bridge_schema.py` as the canonical Bridge evidence contract**

Move Bridge-specific schema construction and Bridge evidence validation into one focused module. The evidence date field must be generated as:

```python
"publication_date": {
    "type": "string",
    "pattern": r"^\\d{4}-\\d{2}-\\d{2}$",
}
```

`validate_bridge_evidence_draft` must enforce exact keys, valid `bc_` format, valid HTTP(S) source URL, exact enum membership, ISO date parsing, and optional claim-reference scope supplied by the caller. It must not create trusted IDs.

- [ ] **Step 4: Make `bridge_request.py` generate package schemas from `bridge_schema.py`**

Replace the duplicated evidence-draft schema builder with the canonical helper. Update `chatgpt_instruction` so that:

```text
Use only verifiable sources with an exact publication date in YYYY-MM-DD form for admitted evidence. Earlier Forge sections may reference only bridge_claim_ref values already defined in landscape_research. collision_research is created after candidates and collision evidence cannot be referenced by extract_assumptions, discover_mechanisms, or forge_candidates.
```

- [ ] **Step 5: Make `bridge_replay.py` call the canonical validator before normalization**

At `_normalize_record`, validate the draft first and preserve the current trusted-ID promotion logic. Keep the phase-order mapping behavior unchanged.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the same unittest command and require all tests to pass.

- [ ] **Step 7: Commit**

```bash
git add src/idea_vending/bridge_schema.py src/idea_vending/bridge_request.py src/idea_vending/bridge_replay.py tests/test_bridge_prompt_contract.py tests/test_bridge_forge.py
git commit -m "fix: align Forge bridge contract with trusted validation"
```

---

### Task 2: Structured Bridge validation errors

**Files:**
- Modify: `app.py`
- Create: `src/idea_vending/bridge_errors.py`
- Test: `tests/test_bridge_http.py`

**Interfaces:**
- Produces: `bridge_error_payload(exc: ValueError) -> dict[str, Any]`
- HTTP error shape: `{ "error": "bridge_import_invalid", "validation_error": {"code": str, "path": str | None, "message": str, "expected_rule": str | None, "actual_summary": str | None, "repair_instruction": str | None} }`

- [ ] **Step 1: Write failing HTTP tests**

Create request cases for an invalid publication date and unknown claim reference and assert the response remains HTTP 400 while containing safe structured `validation_error` data. Assert no traceback, credentials, cookies, or full untrusted source body is returned.

- [ ] **Step 2: Run the focused HTTP tests and verify RED**

```bash
python -m unittest tests.test_bridge_http -v
```

- [ ] **Step 3: Implement a bounded error mapper**

Map known validation codes to user-safe messages. Unknown internal errors remain the generic `bridge_import_invalid` response. Do not serialize exception stack traces.

- [ ] **Step 4: Use the mapper in Forge and Judge import handlers**

Keep existing status-code behavior. Only enrich safe 400-level validation failures.

- [ ] **Step 5: Re-run HTTP tests and verify GREEN**

- [ ] **Step 6: Commit**

```bash
git add app.py src/idea_vending/bridge_errors.py tests/test_bridge_http.py
git commit -m "feat: return actionable bridge validation errors"
```

---

### Task 3: Local Forge/Judge validation UX

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Test: `tests/test_web_contract.py`
- Test: `scripts/verify_browser.py`

**Interfaces:**
- UI nodes: `#forge-validation-status`, `#judge-validation-status`
- Consumes server `validation_error` payload from Task 2

- [ ] **Step 1: Write failing DOM contract tests**

Require both local status nodes and assert `app.js` targets them during import flows rather than only writing the global `#status` node.

- [ ] **Step 2: Extend Chromium verification with one invalid and one valid Forge case**

Invalid Forge result: local panel becomes visible with actionable error text.

Valid Forge result: local panel displays `검증 완료 · 10개 후보` and Judge step becomes visible.

- [ ] **Step 3: Run web/browser tests and verify RED**

Run the repository's existing web contract and Chromium verification commands.

- [ ] **Step 4: Add local status panels and minimal rendering helpers**

Add a helper such as:

```javascript
function renderBridgeValidation(kind, state, detail = '') {
  const target = document.querySelector(kind === 'forge'
    ? '#forge-validation-status'
    : '#judge-validation-status');
  target.dataset.state = state;
  target.textContent = detail;
  target.hidden = false;
}
```

Use server error fields; do not reimplement semantic validation in JavaScript.

- [ ] **Step 5: Run web/browser tests and verify GREEN**

- [ ] **Step 6: Commit**

```bash
git add web/index.html web/app.js web/styles.css tests/test_web_contract.py scripts/verify_browser.py
git commit -m "feat: show bridge validation beside user actions"
```

---

### Task 4: Intent Model contract

**Files:**
- Create: `src/idea_vending/intent_model.py`
- Modify: `src/idea_vending/ideation_contract.py` or the existing provider-neutral request contract used before Forge
- Test: `tests/test_intent_model.py`

**Interfaces:**
- Produces: `validate_intent_model(value: Any) -> dict[str, Any]`
- Produces: `intent_model_schema() -> dict[str, Any]`
- Intent fields: `primary_objective`, `desired_outcome`, `primary_buyer`, `primary_user`, `jobs_to_be_done`, `hard_constraints`, `soft_preferences`, `success_metrics`, `non_goals`, `risk_tolerance`, `automation_target`, `evidence_questions`, `material_unknowns`, `interpretation_notes`

- [ ] **Step 1: Write failing tests for incomplete and contradictory ideas**

Tests must prove:

```python
self.assertIn("material_unknowns", intent)
self.assertIn("hard_constraints", intent)
```

and that an unknown buyer or success metric is preserved as an unknown rather than invented.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement exact schema and validator**

Use explicit arrays for constraints/unknowns and non-empty text for material interpreted fields. The validator must reject extra keys.

- [ ] **Step 4: Run tests and verify GREEN**

- [ ] **Step 5: Commit**

```bash
git add src/idea_vending/intent_model.py src/idea_vending/ideation_contract.py tests/test_intent_model.py
git commit -m "feat: add explicit user intent model"
```

---

### Task 5: Intent interpretation and research planning stage

**Files:**
- Create: `src/idea_vending/intent_planner.py`
- Modify: `src/idea_vending/evolution_runtime_core.py`
- Modify: provider request generation in the existing ideation/research provider boundary
- Test: `tests/test_intent_planner.py`
- Test: `tests/test_evolution_runtime.py`

**Interfaces:**
- Produces: `build_intent_request(raw_idea: str) -> dict[str, Any]`
- Produces: `build_research_plan_request(intent_model: dict[str, Any]) -> dict[str, Any]`
- Research categories: market/customer demand, workflow economics, alternatives/incumbents, feasibility, data quality, regulation/security, blockers, adjacent mechanisms

- [ ] **Step 1: Write failing request-contract tests**

Assert that hard constraints, success metrics, and material unknowns from intent are present in research planning and downstream Forge requests.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement intent interpretation as the first provider-neutral ideation operation**

The model may infer likely interpretation but must put unresolved facts into `material_unknowns`. Contradictory constraints remain explicit.

- [ ] **Step 4: Implement bounded research-plan generation**

The planner returns explicit evidence questions grouped by the required research categories. It must not produce evidence itself.

- [ ] **Step 5: Thread intent and plan through Forge research requests**

Do not remove current landscape/collision stages. Enrich their request context with intent and research questions.

- [ ] **Step 6: Run runtime tests and verify GREEN**

- [ ] **Step 7: Commit**

```bash
git add src/idea_vending/intent_planner.py src/idea_vending/evolution_runtime_core.py tests/test_intent_planner.py tests/test_evolution_runtime.py
git commit -m "feat: drive Forge research from explicit user intent"
```

---

### Task 6: Bridge package support for intent-aware Forge

**Files:**
- Modify: `src/idea_vending/bridge_request.py`
- Modify: `src/idea_vending/bridge_runtime.py`
- Modify: `src/idea_vending/bridge_replay.py`
- Test: `tests/test_bridge_prompt_contract.py`
- Test: `tests/test_bridge_forge.py`

**Interfaces:**
- Forge package includes server-derived intent/research-plan context when available.
- Existing top-level Forge result remains the seven-section result contract unless a versioned Bridge contract change is intentionally introduced.

- [ ] **Step 1: Write failing tests showing Forge instruction is intent-aware**

Assert the package tells ChatGPT to optimize for the supplied objective, constraints, success metrics, and unresolved questions rather than generic ideation.

- [ ] **Step 2: Verify RED**

- [ ] **Step 3: Add intent/research context to package input without expanding trusted result authority**

The package may expose context fields outside `result`, while imported Forge result remains constrained to the seven existing output sections.

- [ ] **Step 4: Re-run bridge tests and verify GREEN**

- [ ] **Step 5: Commit**

```bash
git add src/idea_vending/bridge_request.py src/idea_vending/bridge_runtime.py src/idea_vending/bridge_replay.py tests/test_bridge_prompt_contract.py tests/test_bridge_forge.py
git commit -m "feat: make Forge package intent aware"
```

---

### Task 7: Preserve independent Judge and deterministic authority

**Files:**
- Modify only if required: `src/idea_vending/bridge_request.py`
- Modify only if required: `src/idea_vending/bridge_runtime.py`
- Test: `tests/test_bridge_judge.py`
- Test: `tests/test_runtime_phase_split.py`

**Interfaces:**
- Judge still receives trusted baseline/candidates/evidence/collision state.
- Judge still returns exactly `critiques` and `additional_evidence`.

- [ ] **Step 1: Add regression tests asserting forbidden Judge authority remains forbidden**

The tests must reject Judge-supplied project decision, selected concept, confidence, or human approval fields.

- [ ] **Step 2: Add regression test that split Forge/Judge runtime still reaches the same deterministic decision boundary as the one-shot trusted runtime for the fixture**

- [ ] **Step 3: Run tests and verify behavior**

No production code change is required if current behavior already satisfies these tests.

- [ ] **Step 4: Commit tests or minimal compatibility fix**

```bash
git add tests/test_bridge_judge.py tests/test_runtime_phase_split.py src/idea_vending/bridge_request.py src/idea_vending/bridge_runtime.py
git commit -m "test: preserve independent judge authority boundary"
```

---

### Task 8: Full production verification and live Bridge regeneration

**Files:**
- Modify only verification docs/scripts if required
- Test: full repository suite
- Test: production browser smoke

**Interfaces:**
- End-to-end path: short idea -> intent -> research-driven Forge package -> valid Forge import -> Judge package -> valid Judge import -> official decision -> human approval gate

- [ ] **Step 1: Run the full Python test suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax/security checks used by the repository Production Gate**

Run the existing repository gate commands exactly as defined in CI/verification scripts. Require no secret-bearing output and no diff-check failures.

- [ ] **Step 3: Run real Chromium Bridge verification**

Require both invalid-local-error and valid-Forge-to-Judge flows to pass.

- [ ] **Step 4: Generate a fresh Forge package from the updated production code**

Verify that exported schema and instruction now communicate all trusted validator requirements, including ISO dates and reference scope.

- [ ] **Step 5: Execute one real human-mediated Forge/Judge pilot**

Success criteria:

```text
short idea accepted
intent context generated
Forge package generated
ChatGPT Forge result accepted without manual JSON surgery
10 candidates trusted
Judge package generated
fresh Judge result accepted
official server decision generated
human approval remains separate
```

- [ ] **Step 6: Commit any verification-only documentation updates**

```bash
git add docs scripts tests
git commit -m "docs: record intent intelligence production verification"
```

## Plan self-review

- Spec coverage: all design requirements map to Tasks 1-8.
- Hidden-contract issue: covered in Task 1.
- Local error UX: covered in Tasks 2-3.
- User-intent understanding: covered in Tasks 4-6.
- Independent Judge/deterministic decision boundary: covered in Task 7.
- Production-grade real-browser proof: covered in Task 8.
- No semantic JavaScript validator is introduced.
- No task weakens the current trusted Evidence Graph or server decision authority.
