# Intent Intelligence Forge Design

## Purpose

The Idea Vending Machine must not behave like a thin prompt wrapper. Its job is to infer the user's real objective from incomplete natural language, research the relevant world state, distinguish evidence from assumption, synthesize competing mechanisms and constraints, generate structurally different options, and return outputs that feel tailored to the user's intent while remaining traceable and production-safe.

The product goal is therefore: **high-intelligence understanding + broad evidence synthesis + adversarial verification + deterministic contracts + explicit uncertainty**.

## Product principle

The system should act like a coordinated team of expert roles rather than a single unconstrained generation pass:

1. **Intent Interpreter** — converts the user's raw idea into an explicit intent model.
2. **Research Planner** — decides what must be known before proposing solutions.
3. **Evidence Researcher** — gathers current market, customer, technical, regulatory, competitive, and counter-evidence.
4. **Assumption Breaker** — exposes hidden assumptions and tests inversions.
5. **Mechanism Transferer** — searches adjacent industries for reusable mechanisms.
6. **Candidate Forge** — generates exactly ten structurally distinct candidates.
7. **Independent Judge** — separately criticizes the baseline and candidates.
8. **Deterministic Decision Engine** — produces the official project-level decision from trusted evidence and Judge output.
9. **Human Approval Gate** — keeps final approval with the user.

LLMs perform interpretation, synthesis, research planning, and generative reasoning. Deterministic code owns schemas, IDs, state transitions, validation, provenance, replay safety, and official decision authority.

## Success criteria

A production-ready implementation satisfies all of the following:

- A vague idea is converted into an explicit structured intent model before research starts.
- The system records what the user is trying to achieve, for whom, under which constraints, what success means, what must not happen, and which uncertainties remain.
- Research is driven by unresolved intent questions rather than generic web search.
- Current evidence, counter-evidence, prior art, competitors, failure modes, and material unknowns are all represented explicitly.
- Every material recommendation or candidate can be traced to trusted evidence or is marked as an inference/unknown.
- Forge produces exactly ten canonical candidate families and no official verdict.
- Judge runs in an independent fresh conversation and cannot set the official decision.
- The server rejects malformed or logically impossible references before trusted state changes.
- The same canonical contract generates the ChatGPT-facing result contract and drives server-side validation so hidden validation rules cannot drift.
- Validation errors are shown beside the action that failed with path, rule, actual value, and repair guidance.
- A complete real-browser run reaches Forge validation, Judge request, Judge validation, deterministic decision, and human approval without manual JSON surgery when the model follows the exported contract.

## Architecture

### 1. Intent Model

Introduce a trusted intermediate structure derived from the raw idea before Forge research:

- `primary_objective`
- `desired_outcome`
- `primary_buyer`
- `primary_user`
- `jobs_to_be_done`
- `hard_constraints`
- `soft_preferences`
- `success_metrics`
- `non_goals`
- `risk_tolerance`
- `automation_target`
- `evidence_questions`
- `material_unknowns`
- `interpretation_notes`

The interpreter is not allowed to silently invent missing facts. Missing information remains in `material_unknowns`. The user can still submit a short idea; the system should infer as much as reasonable and mark the rest as uncertain rather than forcing a long questionnaire.

### 2. Research Plan

Research must be generated from the intent model. The planner should create bounded questions in categories such as:

- market/customer demand
- workflow pain and economics
- current alternatives and incumbents
- implementation feasibility
- data availability and quality
- regulation/security constraints
- failure/blocker evidence
- adjacent mechanisms

The research result remains untrusted evidence until it passes the evidence contract.

### 3. Canonical Bridge Contract

The server must have one canonical contract source for Bridge evidence and references. ChatGPT-facing JSON schema is generated from this contract, not manually approximated.

Key rules include:

- `publication_date` must be an ISO calendar date `YYYY-MM-DD` when an evidence record is admitted.
- A source without a verifiable publication date must either use a different source or be represented under an explicitly supported undated-source policy; it must not smuggle prose into a date field.
- Landscape evidence references are available to assumption/mechanism/candidate phases.
- Collision evidence is created after candidates exist and therefore cannot be forward-referenced by earlier Forge sections.
- `bridge_claim_ref` remains an untrusted temporary identifier and is converted server-side into trusted `claim_` and `ev_` IDs.
- Forge cannot inject trusted IDs, candidate IDs, official decisions, confidence, or human approval.

### 4. Reasoning Pipeline

The Forge pipeline is:

`raw idea -> intent interpretation -> research plan -> landscape research -> assumptions -> challenges -> reframes -> mechanism transfer -> ten candidate families -> collision research -> trusted Forge artifact`

Each stage consumes only information available at that point. This removes logically impossible forward references and makes causality inspectable.

### 5. Independent Judge

Judge receives only the trusted Forge artifact and trusted evidence graph. It runs separately from Forge and evaluates:

- baseline plus ten candidates
- every required reality dimension
- strongest evidence for and against
- blockers and unknowns
- cheapest next validation

Judge can add new current evidence using untrusted `bc_` references, but these are validated and promoted server-side before finalization.

Judge never sets `GO`, `MODIFY`, `HOLD`, `KILL`, selected concept, confidence, or human approval.

### 6. Deterministic Decision Authority

Official outcomes remain server-derived. The decision engine consumes trusted evidence coverage, feasibility artifacts, collision state, and independent critiques. It must fail closed when critical evidence or required coverage is missing.

### 7. Error and Repair UX

The current global-status-only behavior is insufficient. Every Bridge import action gets a local validation panel.

A validation error should expose safe structured fields such as:

- `code`
- `path`
- `message`
- `expected_rule`
- `actual_summary`
- `repair_instruction`

The server must not expose stack traces, secrets, raw credentials, or unsafe source content.

The UI should show:

- `검증 중`
- `검증 완료 · 10개 후보`
- or a concrete error beside the Forge result field

For repairable model-output errors, the UI may generate a copyable repair prompt that tells ChatGPT to preserve valid content and correct only the listed contract violations. This is an optional convenience layer; server validation remains authoritative.

## Single source of truth strategy

Do not duplicate validation rules in JavaScript. The browser can perform syntax/size checks, but semantic validation stays server-side.

The Python canonical contract should be responsible for:

- evidence field definitions
- date format requirements
- enums
- reference scopes
- allowed top-level result keys
- candidate-family coverage

`bridge_request.py` exports a machine-readable schema generated from this contract. `bridge_replay.py` and trusted validators consume the same rule definitions or helper functions.

## Quality strategy

### Contract tests

Tests must prove rejection of:

- malformed date values
- unknown or forward `bc_` references
- trusted-ID injection
- missing or duplicate candidate families
- wrong top-level sections
- invalid evidence URLs
- missing collision evidence categories
- Forge-supplied official decision fields

### Intent tests

Tests must prove that:

- incomplete ideas produce explicit unknowns instead of fabricated facts
- hard constraints survive into downstream requests
- research questions reflect the user's objective and constraints
- contradictory user requirements remain visible rather than silently reconciled

### Integration tests

Tests must cover:

`Forge request -> exported contract -> valid Forge import -> trusted Forge -> Judge package`

and

`Judge import -> trusted evaluation -> deterministic official decision`.

### Browser E2E

Chromium must verify that a user can paste a valid Forge result, click validation, see local progress/success, and reach the visible Judge step. A deliberately invalid result must show a local actionable error without requiring the user to scroll to the page header.

## Scope boundaries

This design does not add autonomous purchasing, financial execution, or external side effects. It does not make the model the final authority. It does not add a second JavaScript business-rule validator. It does not attempt to encode all world knowledge locally; current knowledge is obtained through research and retained as evidence with provenance.

## Delivery sequence

1. Align Bridge contract with trusted validators and eliminate hidden rules.
2. Add structured local validation errors and browser UX.
3. Add the explicit Intent Model and intent-driven research-plan stage.
4. Ensure Forge request generation incorporates intent and research-plan context.
5. Preserve independent Judge and deterministic final decision boundaries.
6. Run contract, integration, security, and real-browser E2E gates.
7. Only after all gates pass, regenerate a live Forge package and verify the complete human-mediated production flow.

## Definition of done

The work is complete only when a user can provide a short natural-language idea and the system reliably turns it into a deeply researched, adversarially checked, traceable set of ten distinct options and an independently evaluated official decision path, while clearly exposing uncertainty and never requiring the user to understand internal JSON validation rules.