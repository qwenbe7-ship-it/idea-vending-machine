# 아이디어 자판기 v0.1 Design

## Purpose
아이디어 자판기는 비개발자의 자연어 아이디어를 즉시 코드로 바꾸지 않는다. 먼저 문제, 고객, 자동화 가능성, 구현 가능성, 위험, MVP 범위, 성공조건을 구조화한 뒤 개발 가능한 명세로 변환한다.

## Core rule
**NO GREEN WITHOUT EVIDENCE.** AI의 완료 선언은 증거가 아니다. 테스트와 검증 결과가 있어야 완료다.

## v0.1 Scope
1. 한 줄 이상의 자연어 아이디어 입력
2. 결정론적 Agent MD 분석
3. 구조화된 프로젝트 SPEC 생성
4. Acceptance Criteria 생성
5. 결과를 화면과 JSON으로 확인
6. 단위 테스트 및 브라우저 E2E용 검증 골격
7. GitHub Actions Production Gate

## Non-goals
- SaaS 운영
- 결제/회원가입
- 멀티테넌시
- 실제 외부 LLM API 연결
- 자동 배포

## Architecture
- `src/idea_vending/`: 순수 Python 도메인 로직. 외부 프레임워크에 의존하지 않는다.
- `app.py`: 표준 라이브러리 기반 HTTP 서버. GET `/` 및 POST `/api/analyze` 제공.
- `web/`: 단일 페이지 UI.
- `tests/`: `unittest` 기반 단위/통합 테스트.
- `scripts/verify.py`: 모든 릴리스 게이트를 한 번에 수행.
- `.github/workflows/production-gate.yml`: CI에서 동일 검증 수행.

## Data flow
사용자 아이디어 → 입력 검증 → Agent MD 분석 → MVP 범위/Acceptance Criteria 생성 → JSON 응답 → UI 렌더링.

## Agent MD v0.1
자동화도 A0-A5와 구현가능성 T1-T5를 계산한다. v0.1은 설명 가능한 결정론적 휴리스틱을 사용하며, 향후 LLM 분석기는 동일 인터페이스 뒤에 교체 가능하도록 한다.

## Error handling
- 공백/너무 짧은 아이디어: 400
- 예상하지 못한 서버 오류: 500 + 비민감 메시지
- 분석 결과는 항상 동일한 필드 집합을 반환

## Acceptance Criteria
1. 10자 이상의 아이디어를 제출하면 200과 구조화된 분석을 반환한다.
2. 응답에는 `problem`, `customer`, `automation_level`, `feasibility_level`, `risks`, `mvp_scope`, `acceptance_criteria`가 모두 존재한다.
3. 10자 미만 입력은 400으로 거부한다.
4. 순수 분석 함수는 같은 입력에 같은 출력을 반환한다.
5. `python scripts/verify.py`가 전체 검증의 단일 진입점이다.
6. 검증 실패 시 프로세스가 non-zero로 종료한다.
7. CI가 동일 검증 명령을 실행한다.

## Security baseline
- 사용자 입력을 HTML로 직접 삽입하지 않는다.
- API는 JSON 크기를 제한한다.
- 비밀키를 저장하지 않는다.
- 외부 명령 실행 및 임의 파일 접근 기능은 v0.1에 없다.

## Extension points
- `Analyzer` 인터페이스 뒤에 LLM 분석기 추가
- SPEC/PLAN 파일 내보내기
- Playwright 실제 브라우저 테스트
- GitHub 저장소 자동 생성/PR 생성
