# best_agent_base — 마스터 TODO

> ## 🎯 최종 목적
> **Claude Code(TS·프론트엔드 CLI)의 하네스 기법을 파이썬 백엔드(FastAPI + SQLAlchemy)로 포팅한, 모든 에이전트 프로젝트의 Base 모듈을 만든다.**
>
> - 도메인은 매번 달라지므로 Claude Code를 100% 복제하지 않는다 — 기법(harness, context, ReAct 흐름, 도구 설계 패턴)만 베이스화한다.
> - 산출물은 다른 프로젝트가 `import best_agent_base` 해서 즉시 쓸 수 있는 상태.
> - 마지막엔 **FastAPI 엔드포인트로 에이전트가 노출**되어야 한다 (베이스 수준).
> - **함께 스텝바이스텝으로** 만든다. 한꺼번에 다 짜지 않는다. 각 Phase는 한 번에 하나씩, 사용자와 같이 설계·구현·리뷰.

---

## 🧭 설계 원칙 (모든 Phase에 관통)

CC 분석 문서에서 반복적으로 확인된 5가지 핵심 컨셉. 모든 모듈이 이 원칙을 만족하는지 매 Phase 끝에 점검.

1. **정적/동적 분리 (Caching Boundary)** — 시스템 프롬프트·메시지 어디든 정적 부분은 캐시, 동적 부분은 매 턴 재계산. KV 캐시 적중률이 비용·지연의 핵심.
2. **"안 만들기" 원칙** — 분류기, 라우터, 상태머신 만들지 말 것. 도구 description과 시스템 프롬프트가 분류 역할을 한다.
3. **조용한 정규화 (Silent Normalization)** — 도구 입력 백필·정규화는 모델/사용자가 모르게 코드 레벨에서만.
4. **3그룹/3레이어 병렬 분담** — 어태치먼트 수집(3그룹 `asyncio.gather`), 도구 설계(L1 공통규칙 / L2 description / L3 검증), 권한 판정(allow/ask/deny 3단계).
5. **관찰→교정→재관찰** — 모델 실패 패턴은 `@[MODEL: ...]` 마커로 description·프롬프트에 기록·축적. 프롬프트는 살아있는 튜닝 결과물.

---

## 🏗️ Phase 0 — 프로젝트 골격 & 폴더 구조 설계

> **목적**: 빈 껍데기 + 모듈 트리 + 의존 정리. 코드 본체는 다음 Phase부터.

- [ ] 폴더 구조 합의 (아래 초안 검토·수정)
  ```
  best_agent_base/
  ├── core/                  # 하네스 · 세션 · ReAct 루프
  │   ├── session.py
  │   ├── react_loop.py      # while-true 단순 루프
  │   └── state.py
  ├── prompts/               # 시스템 프롬프트 정적/동적 분리
  │   ├── boundary.py        # __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__
  │   ├── static_sections.py
  │   └── dynamic_sections.py
  ├── attachments/           # 이중 어태치먼트 시스템
  │   ├── collectors/        # 그룹별 수집기들
  │   ├── pipeline.py        # 3그룹 병렬 수집
  │   └── reminders.py       # <system-reminder> 래핑
  ├── tools/
  │   ├── base.py            # Tool 추상 + L3 검증 훅
  │   ├── registry.py        # always-load / deferred 분류
  │   ├── search.py          # ToolSearch 메타 도구
  │   ├── pipeline.py        # 10단계 실행 파이프라인
  │   └── builtins/          # Read, Write, Bash(?), Agent, TaskCreate ...
  ├── hitl/                  # human-in-the-loop
  │   ├── permissions.py     # allow/ask/deny 3단계
  │   └── waiter.py          # asyncio.Event 기반 대기
  ├── llm/
  │   └── gemini.py          # 이미 있음
  ├── context/               # 컨텍스트 관리
  │   ├── compaction.py      # 토큰 임계 시 요약
  │   ├── handoff.py         # 인수인계 메시지
  │   └── filesystem.py      # 외부 메모리(파일) 응용
  ├── api/                   # FastAPI 엔드포인트 (Phase 마지막)
  │   ├── app.py
  │   ├── routes/
  │   └── schemas.py
  └── db/                    # SQLAlchemy 모델 (세션·태스크 영속화)
      ├── models.py
      └── session.py
  ```
- [ ] 의존성 추가 (`uv add fastapi uvicorn sqlalchemy alembic pydantic-settings tiktoken`)
- [ ] 디렉토리·`__init__.py` 빈 껍데기로 생성, import 경로 검증
- [ ] `pyproject.toml`에 `tool.ruff`, `tool.pytest` 최소 설정
- [ ] 환경 변수 로딩 일원화 (`pydantic-settings` 기반 `Settings`)

---

## 🧱 Phase 1 — 시스템 프롬프트 기법 (정적/동적 분리)

> **참조**: `prompt-engineering-techniques.md`, `에이전트-성능-결정요인-총정리.md`

- [ ] 상황별 헤딩 7섹션 골격을 파이썬 데이터 구조로 (Intro / System / Doing tasks / Executing actions / Using tools / Tone & style / Output efficiency)
- [ ] `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커로 정적/동적 경계 구현
- [ ] `dangerous_uncached(name, content, reason)` 헬퍼 — 캐시를 깨는 섹션은 이유까지 명시·기록
- [ ] 조건부 섹션은 무조건 동적 영역으로 (정적에 if 두지 말기)
- [ ] 정적 섹션 해시 → 캐시 적중률 측정용 로깅
- [ ] 단위 테스트: 정적 섹션 안정성, 동적 섹션 변동 허용

---

## 🧊 Phase 2 — KV 캐싱(프롬프트 캐싱) 적용

> **목적**: 모델 호출 시 정적 블록을 캐시 마커와 함께 송신, 적중률을 메트릭으로 노출.

- [ ] 모델별 캐시 컨트롤 추상 (`CachePolicy`) — Gemini 우선, 후일 Anthropic도 차용
- [ ] 메시지 빌더 — `[정적 시스템 | DYNAMIC_BOUNDARY | 동적 시스템 | 대화]` 구조로 송신
- [ ] 캐시 적중·미적중·재계산을 로그/메트릭으로
- [ ] 도구 카탈로그(이름·description) 자체도 정적/동적 분리 (deferred 도구는 동적)
- [ ] 통합 테스트: 같은 세션에서 두 번째 호출 시 정적 부분 비용↓ 확인

---

## 🪝 Phase 3 — 어태치먼트 시스템 (사용자 입력 + ReAct 라운드 양 지점)

> **참조**: `attachment-system.md`, `첨부시스템-이중설계와-TodoWrite-응용비법.md`

- [ ] `Attachment` 베이스 + `<system-reminder>` 자동 래핑
- [ ] **이중 호출 지점** 구현
  - [ ] 사용자 입력 시 (`processUserInput` 등가): `@-mention`, MCP/스킬 파싱
  - [ ] 도구 라운드 후 (`react_loop` 내): 진행 상태 기반 첨부
- [ ] **3그룹 병렬 수집** (`asyncio.gather`)
  - [ ] userInputAttachments
  - [ ] allThreadAttachments (백엔드 상태 기반: DB·세션·할일 등)
  - [ ] mainThreadAttachments (메인 세션 한정 — 서브에이전트엔 X)
- [ ] 조건부 생성 + null 필터링 (해당 없는 첨부는 토큰 낭비 금지)
- [ ] assistant turn 카운터 (도구 라운드 ≠ 유저 턴) — 이후 todo nudge 기반
- [ ] 백엔드 적합 첨부 종류 셀렉션 (initial set):
  - `date_change`, `deferred_tools_delta`, `todo_reminder`, `db_state_summary`(신규), `recent_errors`(신규)

---

## 🛠️ Phase 4 — 도구 베이스 + 도구 설명 패턴(L1/L2/L3)

> **참조**: `에이전트-개발-인사이트_cc분석.md`, `에이전트-성능-결정요인-총정리.md`

- [ ] `Tool` 추상: `name`, `description`, `input_schema(pydantic)`, `validate_input()`, `call()`
- [ ] **3레이어 규칙 분리**
  - L1 (시스템 프롬프트의 공통 규칙)
  - L2 (도구 description: P1 금지·P2 실패조건·P3 대안·P4 if/when·P5 전제)
  - L3 (validate_input의 코드 레벨 검증)
- [ ] description 작성 가이드를 docstring 컨벤션으로 강제
- [ ] 가벼운 빌트인 도구만 우선 구현
  - 일반 도구 1~2: `Echo`, `Calc` (혹은 단순 `HttpGet`)
  - 도구 서치 1: `ToolSearch`
  - 서치 대상 3: 예) `WeatherFetch`, `JsonValidate`, `MarkdownRender`
  - 그리고 카피해 올 도구: `ReadFile`, `WriteFile`, `EditFile`, `Agent`, `TaskCreate`/`TaskUpdate`/`TaskList`
- [ ] 도구별 검증 실패 메시지가 모델이 다음 행동을 결정 가능한 형태인지 점검 (정상 에러 ≠ throw)

---

## 🔄 Phase 5 — ReAct 루프 + 흐름 기반 도구 컨트롤

> **참조**: `claude-code-research.md`, `에이전트-개발-인사이트_cc질의.md`

- [ ] `ReactLoop` — `async while True` + 토큰 임계 도달 / 종료 신호 / 스텝 상한
- [ ] 읽기 전용 도구 병렬(`asyncio.gather`) / 쓰기 도구 순차 분리 (도구 메타데이터 기반)
- [ ] 도구 호출 순서가 어그러지면 description 패턴 P1·P5에 의지 + 코드 가드(예: Edit 전 Read 강제) 한 줄
- [ ] 흐름을 끊는 도구(`SendUserMessage`, HITL 권한 대기)는 루프에 명시적 yield 포인트
- [ ] FastAPI 스트리밍을 염두에 둔 `async generator` 인터페이스

---

## 🔍 Phase 6 — 도구 서치 시스템 (Always-load / Deferred)

> **참조**: `toolsearch-시스템.md`

- [ ] `ToolRegistry` — 도구를 `always_load` / `deferred` 태그로 분류
- [ ] `ToolSearch` 메타 도구
  - `select:Name1,Name2` 직접 선택
  - 키워드 검색 → 상위 N개 schema 반환
  - 반환 형식은 모델이 곧장 호출 가능하게 (description + parameters 동시)
- [ ] 새 도구 로드 시 `deferred_tools_delta` 어태치먼트 발화
- [ ] 캐시 영향 측정 — deferred 도구가 정적 카탈로그를 깨지 않음을 검증

---

## 👤 Phase 7 — 유저 질문 어태치먼트 (입력 시점 처리)

> **참조**: `attachment-system.md` 의 userInputAttachments 부분

- [ ] `@path/to/file` → 파일 내용 자동 첨부
- [ ] `@db:table.row_id` 같은 백엔드 특화 멘션 (FastAPI/SQLAlchemy 컨텍스트)
- [ ] 첨부 추출 후 메시지에서 토큰 짤림 방지 (원본 보존 + system-reminder로 부가)
- [ ] 입력 검증 — 권한 없는 리소스 멘션은 거부 또는 마스킹

---

## ✋ Phase 8 — 휴먼 인 더 루프 (권한 + 비동기 대기)

> **참조**: `human-in-the-loop.md`

- [ ] `Permission` — 3단계 판정 (deny / ask / allow), 모드(default / acceptEdits / bypass / dontAsk / auto)
- [ ] `asyncio.Event` 기반 `Waiter` (Promise + resolve의 파이썬 등가)
- [ ] `resolve_once` 보장 (이중 응답 방어)
- [ ] FastAPI 측: 별도 `/permissions/{request_id}/respond` 엔드포인트로 외부 응답 수신 → Waiter 해제
- [ ] auto 모드: 연속 N회 거부 시 자동 해제 정책

---

## 🧹 Phase 9 — 컨텍스트 관리 (도구 결과 / 파일시스템 / 인수인계)

> **참조**: `에이전트-개발-인사이트_cc분석.md`, `claude-code-research.md`

- [ ] 도구 결과의 사이즈 가드 — 큰 결과는 요약 + 원본은 파일시스템(또는 DB BLOB)에 저장 후 핸들 반환
- [ ] 토큰 카운터 (`tiktoken` 또는 모델 자체 카운터)
- [ ] 임계 도달 시 자동 컴팩션(요약) — 시스템 메시지 형태로 주입
- [ ] 파일시스템 응용 — 외부 메모리(`./.agent_state/`)에 장기 컨텍스트 저장·읽기
- [ ] 인수인계 (`/handoff` 등가) — 다음 세션이 그대로 받을 수 있는 핸드오프 문서 자동 생성
- [ ] DB(SQLAlchemy)에 세션·턴·도구호출 영속화 (재현·디버깅용)

---

## 🚦 Phase 10 — 도구 실행 10단계 파이프라인 (검증 강화)

> **참조**: `도구-실행-10단계-파이프라인.md`

`tools/pipeline.py`에 다음 단계 구현:

- [ ] 1. Pydantic 스키마 검증
- [ ] 2. `validate_input()` 도구별 검증
- [ ] 3. (선택) 안전성 분류기 — 쓰기 도구만 LLM/룰 분류
- [ ] 4. 입력 정규화 (backfill — 훅·권한 시스템이 볼 수 있게)
- [ ] 5. pre-hook (사용자 정의 훅)
- [ ] 6. 권한 확인 (Phase 8 연동)
- [ ] 7. 실행 (`call()`)
- [ ] 8. post-hook
- [ ] 9. 결과 정규화·요약 (Phase 9 연동)
- [ ] 10. 로깅·감사 (DB 기록)

---

## 🌐 Phase 11 — FastAPI 노출 (베이스 API)

> **목적**: 위 모든 모듈이 동작하는 최소 API. 베이스이므로 1 엔드포인트 + 스트리밍 + 권한 콜백.

- [ ] `POST /agent/sessions` — 세션 생성
- [ ] `POST /agent/sessions/{id}/messages` — 메시지 전송 + SSE/WS 스트리밍 응답
- [ ] `POST /agent/permissions/{req_id}/respond` — HITL 응답
- [ ] `GET /agent/sessions/{id}/state` — 디버깅용 세션 상태
- [ ] DB(SQLAlchemy) 세션·턴·툴콜 영속화 적용
- [ ] OpenAPI 스키마 정상 생성 + 예제 cURL/HTTPie 문서

---

## ✅ 마감 점검 (Definition of Done — Base)

- [ ] `uv run uvicorn best_agent_base.api.app:app --reload` 로 즉시 동작
- [ ] 새 프로젝트가 `from best_agent_base import ReactLoop, ToolRegistry, build_app` 한 번으로 시작 가능
- [ ] 정적/동적 분리 → 두 번째 호출 시 캐시 적중 확인
- [ ] HITL 외부 응답으로 도구 실행 재개 확인
- [ ] 도구 서치로 deferred 도구 동적 호출 가능 확인
- [ ] 핸드오프 문서로 다른 세션이 작업 이어받기 가능 확인

---

## 🤝 진행 방식 합의

- **전체 작업은 `js-super` 플러그인만 사용해서 진행한다.** (superpowers 등 다른 워크플로우 플러그인은 쓰지 않음)
- **Phase 1개 = `js-super` 풀 사이클 1회.** (`/brainstorm` 부터 `finishing-a-development-branch` 까지 한 바퀴를 돌고 다음 Phase로 넘어간다. 중간 단계 임의 생략 금지 — 단, `/api-test` 는 위 명시 조건일 때만 스킵 허용.)
- 모든 Phase는 `js-super`의 표준 파이프라인을 따른다:

  ```
  /brainstorm   → docs/features/YYYY-MM-DD-<slug>/<slug>-requirements.md
       ↓
  /design       → <slug>-tech-design.md       (verifying-spec 게이트 통과)
       ↓
  /write-plan   → <slug>-implementation-plan.md  (단계별 TDD, verifying-spec 게이트 통과)
       ↓
  /execute-plan → 5-step discipline 으로 구현
                  (snapshot → risk-annotation 6-체크 → apply →
                   RISK 주석 검증 → change-history 기록)
       ↓
  /api-test     → API 자동 테스트 (pytest 시나리오 자동 생성/실행)
                  ※ 상황에 따라 스킵 가능 (API 노출이 없는 Phase, 인터페이스/추상만 다루는
                    Phase, 외부 의존이 큰 Phase 등은 건너뛴다)
       ↓
  finishing-a-development-branch
  ```

- 변경 시: `js-super:change-propagation` 으로 상위 MD부터 cascade, `change-history` 자동 기록.
- 위험 코드: `js-super:risk-annotation` 으로 `# ⚠️ RISK(...)` 주석 자동 부착.
- 독립 작업 병렬화 가능하면 `js-super:dispatching-parallel-agents` / `subagent-driven-development`.
- 워크트리 필요 시 `js-super:setting-up-worktrees` (`.worktrees/<branch>` + `.env*` 자동 복사).
- 한 Phase = 한 세션 단위 작업. 시작 전에 **사용자가 "다음 Phase 가자"** 라고 신호.
- 의문/대안/트레이드오프가 보이면 코드 작성 전에 먼저 **2~3문장으로** 제시하고 결정 받기.
- CC의 src/는 아직 안 본다 — 문서 기준으로 먼저 짜고, 막히면 그때 src 발췌해서 비교.
