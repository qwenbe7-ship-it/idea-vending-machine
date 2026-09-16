# 아이디어 자판기 (Idea Vending Machine)

비개발자의 자연어 아이디어를 바로 코드로 바꾸지 않고, 먼저 **문제 → 시장 → 근거 → 반대근거 → 아이디어 진화 → 경영 의사결정 → 승인 → 개발 명세**로 연결하는 AI Innovation Due Diligence & Idea Evolution Engine을 목표로 합니다.

> **NO GREEN WITHOUT EVIDENCE** — AI의 "완성했습니다"는 증거가 아닙니다. 테스트와 검증이 통과해야 완료입니다.

## 현재 기준선

### v0.2 — Development Package

- 자연어 아이디어 입력
- Agent MD 기반 A0–A5 자동화도 분석
- T1–T5 구현가능성 분석
- 예상 고객·핵심 위험·MVP 범위 생성
- 검증 가능한 Acceptance Criteria 생성
- 결정론적 `spec.md` · `design.md` · `plan.md` 생성
- 브라우저에서 세 문서 미리보기 및 개별 다운로드
- 웹 UI 및 JSON API
- 테스트/보안계약/컴파일을 묶은 Production Gate

같은 아이디어와 같은 분석 결과는 같은 개발 문서 패키지를 생성합니다. 생성 문서는 서버 파일시스템에 자동 저장하지 않고 API로 반환한 뒤 브라우저에서만 Blob 다운로드합니다.

### v0.3 PR A — Executive Decision Foundation

아이디어를 바로 개발 문서로 보내기 전에 **대표이사 관점의 혁신 의사결정 보고서**를 거치기 위한 결정론적 계약입니다.

- 원문 아이디어를 변형하지 않고 보존하는 `Evolution State`
- `GO` / `MODIFY` / `HOLD` / `KILL` 의사결정 상태
- 앞부분 핵심 요약 + 뒷부분 상세 근거로 분리된 보고서 스키마
- 찬성 이유 3개와 반대 이유 3개를 함께 요구하는 Executive Brief
- 20개 canonical 상세 분석 섹션
- 보고서 claim ID와 state-level evidence reference의 추적성 검사
- 명시적인 사람의 `proceed` 승인 전 개발 패키지 생성 차단
- `HOLD`와 `KILL`에서 `spec.md` / `design.md` / `plan.md` handoff 구조적 차단
- 기존 v0.2 `/api/analyze`와 `/api/package` 동작 유지

### v0.3 PR B — Evidence Graph + Provider-neutral Research Engine

PR B는 실제 검색 결과를 장문의 텍스트로 바로 신뢰하지 않습니다. 모든 외부 근거는 먼저 **Evidence Record**로 정규화된 뒤 검증되어야 합니다.

각 Evidence Record는 최소 다음 정보를 보존합니다.

- `evidence_id` / `claim_id`
- 주장과 출처 제목·URL·publisher
- publication date / retrieved date
- geography / population 또는 market definition
- evidence type
- `supports` / `contradicts` / `neutral`
- confidence tier `A/B/C/D`
- freshness status
- 관련 candidate IDs
- provider metadata
- 명시적으로 untrusted 처리되는 raw provider content

Evidence Graph는 동일 assessment 안에서 evidence ID와 claim ID 중복을 허용하지 않습니다.

## 시장규모 무결성 규칙

시장규모 숫자는 보기 좋은 한 숫자를 만드는 것보다 **정의 차이를 보존하는 것**을 우선합니다.

- 기준연도와 기준값을 명시합니다.
- 전망이 있으면 전망연도와 전망값을 함께 기록합니다.
- geography와 market definition을 필수로 기록합니다.
- 보고된 값인지(`reported`), 계산한 값인지(`derived`), 시나리오인지(`scenario`) 구분합니다.
- 서로 다른 market definition, geography, currency/unit, base year를 가진 추정치는 평균내지 않습니다.
- 호환되지 않는 시장 추정치는 definition별 범위와 차이로 표시합니다.

즉 `$2B`와 `$8B`라는 두 보고서가 서로 다른 시장을 측정한다면 `$5B 시장`이라고 만들어내지 않습니다.

## 두 번의 Research Pass

v0.3은 리서치를 한 번에 끝내지 않습니다.

### Pass 1 — Landscape Research

아이디어 진화 전에 문제와 현실을 이해합니다.

- 문제의 실제 존재와 크기
- customer / buyer
- 현재 workflow와 alternatives
- 시장 단계
- 시장 규모와 성장
- regulation / timing
- 현재 기술능력
- **Evidence Against / counter-evidence**

Landscape research request는 counter-evidence 범주가 없으면 유효하지 않습니다.

### Pass 2 — Collision Research

후보 아이디어가 만들어진 뒤 현실과 다시 충돌시킵니다.

최소 다음 범주를 요구합니다.

- `prior_art`
- `competitors`
- `failure_or_blockers`

이를 통해 이미 존재하는 제품, 실패사례, 기술·규제 블로커 등을 확인합니다.

## Provider-neutral Research Engine

현재 Research Engine은 특정 검색업체나 특정 LLM에 종속되지 않습니다.

```text
Search / Research Provider
        ↓
Provider Adapter
        ↓
Normalized Evidence Record
        ↓
Evidence Graph Validation
        ↓
Coverage / Counter-evidence Audit
        ↓
Evolution State evidence_refs
        ↓
Executive Innovation Report
```

Provider가 반환한 raw object는 Evidence Record validation을 우회할 수 없습니다. provider text는 항상 untrusted data로 보존되며 실행 지시로 취급하지 않습니다.

라이브 웹 검색 adapter를 PR B에 직접 넣지 않은 이유는 **검색 제공자를 바꾸더라도 evidence quality contract와 경영 판단 기준이 변하지 않도록 하기 위해서**입니다.

## Evidence Coverage Gate

Research 결과가 많다고 의사결정 준비가 끝난 것은 아닙니다.

현재 evidence audit은 다음을 확인합니다.

- support evidence 수
- contradiction evidence 수
- neutral evidence 수
- A/B/C/D confidence 분포
- stale / historical evidence 수
- 아직 근거가 없는 material claim

찬성 근거만 있고 반대 근거가 없거나, material claim이 미해결이면 `decision_ready=false`입니다.

### v0.3 PR C — Reframing + Candidate Forge

PR C는 처음으로 아이디어를 실제로 **재구성하고 진화시키는 창의적 지능 계층**을 추가합니다. 단, 생성 모델이 공식 상태나 최종 사업 판단을 직접 소유하지 못하도록 Hybrid Expert Forge 구조를 사용합니다.

```text
Evidence Graph
  ↓
Assumption Map
  ↓
Perspective Transformations
  ↓
Cross-Industry Mechanism Transfer
  ↓
Candidate Forge
  ↓
Deterministic Admission Gates
  ↓
Collision Research
  ↓
PR D Independent Evaluator
```

핵심 규칙:

- provider 출력은 항상 **untrusted structured data**입니다.
- `assumption_id`, `transfer_id`, `candidate_id`, Collision Research request ID는 trusted deterministic code가 생성합니다.
- 중요한 사실 주장은 기존 Evidence Graph `claim_id`로 추적되어야 합니다.
- 근거가 부족한 결정적 질문은 사실로 승격하지 않고 Collision Research request로 전환합니다.
- 후보는 `adjacent_innovation`, `category_shift`, `zero_based_reinvention`, `axion_candidate` 네 family를 사용합니다.
- 단순 이름·기능 차이만 있는 후보는 diversity audit에서 탈락합니다.
- 모든 후보는 `constraint → intervention → workflow/incentive change → economic effect → buyer value → value capture` 인과사슬을 명시해야 합니다.
- 후보 family가 적용 불가능하다면 이유를 명시해야 합니다.
- PR C는 **우승 후보, 점수, GO/MODIFY/HOLD/KILL 결론을 만들지 않습니다.** 독립 평가와 최종 사업 판단은 PR D 책임입니다.

Candidate Set은 다음 deterministic Gate를 모두 통과해야 `forge_ready=true`가 됩니다.

- schema
- evidence traceability
- reframe readiness
- mechanism integrity
- causal value chain
- structural diversity
- family coverage
- explicit unknowns / validation questions

### v0.3 PR D — Independent Evaluator + Decision Engine

PR D는 Candidate Forge와 분리된 **독립 투자심사 계층**입니다. 생성 모델의 자기평가나 설득 문장을 공식 판단으로 사용하지 않고, 독립 critique를 Evidence Graph와 deterministic hard gate에 통과시킨 뒤에만 사업 결론을 만듭니다.

```text
Raw-Idea Baseline + Candidate Set
        ↓
Independent Evaluator Request
        ↓
Untrusted Critique Output
        ↓
Evidence / Counter-evidence Validation
        ↓
Feasibility / Collision / Blocker Gates
        ↓
Evolution Delta / Strict Dominance
        ↓
Deterministic Decision Engine
        ↓
GO / MODIFY / HOLD / KILL
```

핵심 규칙:

- 원안을 별도 content-addressed baseline으로 보존하여 `GO`와 `MODIFY`를 구분합니다.
- evaluator는 정확히 10개 차원을 `strong` / `mixed` / `weak` / `unknown`으로 평가하지만 공식 총점·랭킹은 만들지 않습니다.
- evaluator/provider 출력은 항상 untrusted이며 `decision`, `confidence`, `selected_concept_id`, trusted ID를 직접 설정할 수 없습니다.
- `GO`는 **원안 유지**, `MODIFY`는 **검증된 진화 후보 채택**입니다.
- 결정적 근거가 부족하거나 material collision/unknown이 남아 있으면 `HOLD`입니다.
- 누락된 근거만으로는 절대 `KILL`하지 않습니다. `KILL`은 원안과 모든 후보가 evidence-backed decisive failure로 탈락할 때만 허용됩니다.
- `T1`은 positive decision을 만들 수 없고, 미해결 `T2`는 원칙적으로 `HOLD`입니다.
- `GO`/`MODIFY`에 `low` confidence는 허용하지 않습니다.
- 둘 이상의 진화 후보가 동시에 적합한 경우 한 후보가 다른 후보들을 strict dominance하지 못하면 가짜 순위를 만들지 않고 `HOLD`합니다.
- PR D는 사람을 대신해 `human_decision=proceed`를 설정하지 않습니다.
- 기존 `HOLD/KILL → v0.2 handoff 차단` 계약은 그대로 유지됩니다.

## v0.3 목표 흐름

```text
RAW IDEA
  ↓
LANDSCAPE RESEARCH
  ↓
EVIDENCE GRAPH
  ↓
ASSUMPTION MAP / REFRAME
  ↓
MECHANISM TRANSFER / CANDIDATE FORGE
  ↓
DETERMINISTIC ADMISSION
  ↓
COLLISION RESEARCH
  ↓
INDEPENDENT EVALUATION + DECISION ENGINE (PR D)
  ↓
EXECUTIVE INNOVATION REPORT / UX (PR E)
  ↓
GO / MODIFY / HOLD / KILL
  ↓
HUMAN DECISION
  ├─ GO/MODIFY + proceed → v0.2 SPEC / DESIGN / PLAN
  └─ HOLD/KILL → development handoff blocked
```

PR D까지는 **근거 계층 + 아이디어 진화 + 독립 투자심사 + 공식 decision contract**를 구현합니다. 실제 live provider adapter와 최종 Executive UX/E2E 연결은 PR E 범위입니다.

## 빠른 실행

Python 3.11 이상만 있으면 추가 패키지 설치가 필요 없습니다.

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

현재 공개 사용자 UI는 아직 v0.2 흐름을 유지합니다.

```text
아이디어 입력
  ↓
Agent MD 분석
  ↓
문제 / 고객 / A0-A5 / T1-T5 / 위험 / MVP / Acceptance Criteria
  ↓
개발 패키지 생성
  ↓
spec.md + design.md + plan.md
  ↓
각 문서 미리보기 / 다운로드
```

v0.3의 Research/Evolution/Evaluation 계층은 PR E에서 실제 provider 및 Executive UX와 연결합니다.

## 검증

릴리스 전에 반드시 다음 명령을 실행합니다.

```bash
python scripts/verify.py
```

정상 완료의 마지막 출력은 다음과 같습니다.

```text
GREEN WITH EVIDENCE
```

하나라도 실패하면 릴리스하지 않습니다.

## API

### `POST /api/analyze`

요청 예시:

```json
{
  "idea": "업로드된 영수증에서 항목을 추출하고 표로 정리하는 자동화 도구"
}
```

응답에는 다음 필드가 포함됩니다.

- `problem`
- `customer`
- `automation_level`
- `feasibility_level`
- `risks`
- `mvp_scope`
- `acceptance_criteria`

### `POST /api/package`

요청 형식은 `/api/analyze`와 같습니다. 성공 응답은 기존 분석 결과와 세 Markdown 문서를 함께 반환합니다.

```json
{
  "analysis": {
    "automation_level": "A4",
    "feasibility_level": "T5"
  },
  "documents": {
    "spec.md": "# Product Specification ...",
    "design.md": "# System Design ...",
    "plan.md": "# Implementation Plan ..."
  }
}
```

생성 패키지는 정확히 `spec.md`, `design.md`, `plan.md` 세 파일로 구성되며, 세 문서는 동일한 deterministic Project ID를 공유합니다.

## 프로젝트 구조

```text
src/idea_vending/analyzer.py              Agent MD 분석 엔진
src/idea_vending/package_generator.py     결정론적 개발 문서 생성기
src/idea_vending/evolution_schema.py      v0.3 상태·CEO 보고서 계약
src/idea_vending/evolution_handoff.py     승인된 결과의 v0.2 handoff gate
src/idea_vending/evidence_graph.py        Evidence Record/Graph + market integrity/audit
src/idea_vending/research_engine.py       provider-neutral two-pass research orchestration
src/idea_vending/evidence_attachment.py   Evidence Graph ↔ Evolution State traceability
src/idea_vending/reframing.py             Assumption Map + perspective transformation contracts
src/idea_vending/mechanism_transfer.py    cross-industry causal mechanism transfer contract
src/idea_vending/ideation_contract.py     provider-neutral untrusted ideation boundary
src/idea_vending/candidate_forge.py       candidate contract + diversity/causal/admission gates
src/idea_vending/baseline_contract.py     content-addressed raw-idea comparison baseline
src/idea_vending/evaluator_contract.py    independent evaluator critique/evidence schema
src/idea_vending/independent_evaluator.py provider-neutral untrusted evaluator boundary
src/idea_vending/decision_engine.py       deterministic hard gates + official decision engine
web/                                      비개발자용 현재 v0.2 단일 페이지 UI
tests/                                    단위·HTTP·웹·보안·v0.3 계약 테스트
scripts/verify.py                         Production Gate 단일 진입점
docs/superpowers/                         설계와 구현 계획
.github/workflows/                        GitHub Actions 검증
```

## 의도적으로 제외한 것

SaaS 운영, 결제, 회원가입, 자동배포, 자동 코드 실행은 포함하지 않습니다. PR D에는 **실시간 검색 provider API, 실제 외부 LLM adapter, 새로운 v0.3 Executive UX, 영속 데이터베이스, 인증/결제 계층**을 포함하지 않습니다.

PR E에서 최종 Executive UX와 전체 v0.3 pipeline/E2E Production Gate를 연결합니다.