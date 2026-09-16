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

## v0.3 목표 흐름

```text
RAW IDEA
  ↓
LANDSCAPE RESEARCH
  ↓
EVIDENCE GRAPH
  ↓
REFRAME / IDEA EVOLUTION
  ↓
COLLISION RESEARCH
  ↓
EXECUTIVE INNOVATION REPORT
  ↓
GO / MODIFY / HOLD / KILL
  ↓
HUMAN DECISION
  ├─ GO/MODIFY + proceed → v0.2 SPEC / DESIGN / PLAN
  └─ HOLD/KILL → development handoff blocked
```

PR B까지는 Reframe/Candidate Forge/독립 AI Evaluator/UI를 아직 구현하지 않습니다. 먼저 이후 지능이 의존할 **검증 가능한 근거 계층**을 고정합니다.

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

v0.3 Research/Evidence 계층은 후속 PR에서 실제 provider 및 Executive UX와 연결합니다.

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
web/                                      비개발자용 현재 v0.2 단일 페이지 UI
tests/                                    단위·HTTP·웹·보안·v0.3 계약 테스트
scripts/verify.py                         Production Gate 단일 진입점
docs/superpowers/                         설계와 구현 계획
.github/workflows/                        GitHub Actions 검증
```

## 의도적으로 제외한 것

SaaS 운영, 결제, 회원가입, 자동배포, 자동 코드 실행은 포함하지 않습니다. PR B에는 **실시간 검색 provider API, 외부 LLM provider, Candidate Forge, Reframing Engine, 독립 투자심사 Evaluator, 새로운 v0.3 UI, 영속 데이터베이스**도 포함하지 않습니다.

이 기능들은 Evidence Graph와 Research Contract가 Production Gate를 통과한 뒤 별도 단계에서 추가합니다.
