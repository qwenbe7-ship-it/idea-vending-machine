# 아이디어 자판기 (Idea Vending Machine)

비개발자의 자연어 아이디어를 바로 코드로 바꾸지 않고, 먼저 **문제 → 고객 → 자동화도 → 구현가능성 → 위험 → MVP 범위 → Acceptance Criteria → 개발 문서 패키지**로 변환하는 개발 프런트도어입니다.

> **NO GREEN WITHOUT EVIDENCE** — AI의 "완성했습니다"는 증거가 아닙니다. 테스트와 검증이 통과해야 완료입니다.

## v0.2에서 되는 것

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

## 빠른 실행

Python 3.11 이상만 있으면 추가 패키지 설치가 필요 없습니다.

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 사용 흐름

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
src/idea_vending/analyzer.py            Agent MD 분석 엔진
src/idea_vending/package_generator.py   결정론적 개발 문서 생성기
web/                                    비개발자용 단일 페이지 UI
tests/                                  단위·HTTP·웹·보안 계약 테스트
scripts/verify.py                       Production Gate 단일 진입점
docs/superpowers/                       설계와 구현 계획
.github/workflows/                      GitHub Actions 검증
```

## 의도적으로 제외한 것

SaaS 운영, 결제, 회원가입, 외부 LLM API, 자동배포, 자동 코드 실행은 포함하지 않습니다. v0.2의 목표는 **한 아이디어를 재현 가능한 개발 명세 패키지로 변환하는 것**입니다.
