# 아이디어 자판기 (Idea Vending Machine)

비개발자의 자연어 아이디어를 바로 코드로 바꾸지 않고, 먼저 **문제 → 고객 → 자동화도 → 구현가능성 → 위험 → MVP 범위 → Acceptance Criteria**로 변환하는 개발 프런트도어입니다.

> **NO GREEN WITHOUT EVIDENCE** — AI의 "완성했습니다"는 증거가 아닙니다. 테스트와 검증이 통과해야 완료입니다.

## v0.1에서 되는 것

- 자연어 아이디어 입력
- Agent MD 기반 A0–A5 자동화도 분석
- T1–T5 구현가능성 분석
- 예상 고객·핵심 위험·MVP 범위 생성
- 검증 가능한 Acceptance Criteria 생성
- 웹 UI 및 JSON API
- 테스트/보안계약/컴파일을 묶은 Production Gate

## 빠른 실행

Python 3.11 이상만 있으면 추가 패키지 설치가 필요 없습니다.

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

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

`POST /api/analyze`

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

## 프로젝트 구조

```text
src/idea_vending/      결정론적 Agent MD 도메인 엔진
web/                   비개발자용 단일 페이지 UI
tests/                 단위·HTTP·보안 계약 테스트
scripts/verify.py      Production Gate 단일 진입점
docs/superpowers/      설계와 구현 계획
.github/workflows/     GitHub Actions 검증
```

## v0.1에서 의도적으로 제외한 것

SaaS 운영, 결제, 회원가입, 외부 LLM API, 자동배포는 포함하지 않습니다. 먼저 작은 입력부터 끝까지 재현 가능하게 검증하는 것이 목표입니다.
