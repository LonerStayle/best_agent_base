# best_agent_base — 마스터 TODO

> ## 🎯 최종 목적
> **Claude Code(TS·프론트엔드 CLI)의 하네스 기법을 파이썬 백엔드(FastAPI + SQLAlchemy)로 포팅한, 모든 에이전트 프로젝트의 Base 모듈을 만든다.**
>
> - 도메인은 매번 달라지므로 Claude Code를 100% 복제하지 않는다 — 기법(harness, context, ReAct 흐름, 도구 설계 패턴)만 베이스화한다.
> - 산출물은 다른 프로젝트가 `import best_agent_base` 해서 즉시 쓸 수 있는 상태.
> - 마지막엔 **FastAPI 엔드포인트로 에이전트가 노출**되어야 한다 (베이스 수준).
> - **함께 스텝바이스텝으로** 만든다. 한꺼번에 다 짜지 않는다. 각 Phase는 한 번에 하나씩, 사용자와 같이 설계·구현·리뷰.

---

## 📜 출발점 — 원작자 의도 & 인터페이스 합의

### 원작자(사용자)가 처음 던진 요구 (요약)

- 클로드코드 소스를 가지고 있다. 타입스크립트 기반이지만 본인은 파이썬 개발자.
- 세계 최고 수준의 에이전트 기법을 파이썬으로 옮겨, **모든 작업의 Base** 가 되길 원함.
- 에이전트마다 도메인이 다르니 100% 복제는 안 되지만, **클로드코드가 차용한 기술을 베이스로 응용**.
- 클로드코드는 React 패턴을 고도로 설계 + 미친 컨텍스트 관리력. 그것을 가능하게 하는 건 **하네스**.
- 클로드코드는 100% 프론트엔드, 본인은 **백엔드(FastAPI, SQLAlchemy 등)** 로 작용하길 원함 → 어느 정도 마이그레이션.
- 만들고 싶은 기술 (10가지):
  0. 전체 프로젝트 세팅
  1. 시스템 프롬프트 기법
  2. KV 캐싱 (프롬프트 캐싱)
  3. React 패턴 중간 컨텍스트 어태치먼트 기법
  4. 도구의 심도 있는 설명 + 검증 패턴 (호출 순서 보호)
  5. React 흐름 기반 도구 컨트롤
  6. 도구 서치 기법
  7. 유저 질문 어태치먼트 기법
  8. 유연한 HITL 컨트롤 설계
  9. 컨텍스트 관리 기법 (도구 결과 컨트롤, 파일시스템 응용, 인수인계법)
  10. 심도 있는 도구 실행 파이프라인
- 도구는 베이스 수준이라 **가볍게** — 일반 1~2개 + 도구 서치 1개 + 서치 대상 3개 + 에이전트/투두/파일 R·W 도구는 잘 카피.
- 최종적으로 **API까지** 나오길 (베이스 수준이지만).
- 본인의 **실력 향상**도 목적 → 한꺼번에 다 해주지 말고 스텝바이스텝, 함께 만들어가는 방식.

### "전체적으로 인터페이스를 뚫어놓으라는 거 맞지?" 에 대한 합의

> **Base = 인터페이스·계약(추상 클래스 / Protocol / Pydantic 스키마 / 엔드포인트 시그니처)을 끝까지 뚫어놓는 작업.**

- 각 Phase의 산출물은 **"동작하는 두꺼운 구현"이 아니라 확장 포인트가 명확한 골격**.
  - `Tool`, `Attachment`, `Permission`, `Waiter`, `CachePolicy`, `Hook`, `Memory`, `Subagent` 같은 추상/Protocol.
  - 빌트인 도구는 **참조 구현 한두 개**로 패턴만 보여줌.
  - FastAPI 라우트도 시그니처·스트리밍 형태만 잡고 비즈니스 로직은 비워둠.
- 다른 프로젝트가 갖다 쓸 때 **상속·구현·교체**만 하면 되도록.
- 내부에서 만나는 모든 경계는 **인터페이스 먼저 → 참조 구현 → 테스트** 순서.

> 이 원칙은 **모든 Phase 의 acceptance 기준** 으로 작동한다 — Phase 종료 시 "추상이 명확한가? 교체 가능한가?" 를 먼저 점검.

---

## 📚 참조 베이스 (Source of Truth)

본 프로젝트의 모든 기법·패턴·인터페이스 결정은 다음 분석 자료에서 출발한다.

- **루트**: `/Users/goldenplanet/jinsup_space/CC/`
- **하위 구조** — 분석 .md 들은 모든 단계의 베이스(특히 `/brainstorm`, `/design`, `/write-plan`), **`src/` 는 구현 단계(`/execute-plan`) 진입 시 분석 .md 와 함께 필수 참조** (.md 는 의도·이유, src 는 ground truth — 둘 다 본다):

  ```
  CC/
  ├── claude-code-research.md            # 전체 아키텍처 · ReAct 루프
  ├── claude-code-research_v2.md         # v1 + 멀티턴 레저/10단계 보강
  ├── 에이전트-성능-결정요인-총정리.md   # 14 프롬프트 기법 · 3레이어 도구 설계
  ├── 도구-실행-10단계-파이프라인.md     # checkPermissionsAndCallTool 10단계
  ├── 첨부시스템-이중설계와-TodoWrite-응용비법.md   # 이중 어태치먼트 · TodoWrite
  ├── attachment-system.md               # 30+ 어태치먼트 자동 수집
  ├── human-in-the-loop.md               # 권한 3단계 + Promise/resolve
  ├── prompt-engineering-techniques.md   # 7섹션 · 캐시 경계 마커
  ├── 시스템프롬프트-7섹션-요약.md       # 7 섹션 각각의 주제·핵심·역할 (Phase 1 1차 자료)
  ├── todo-task-system-analysis.md       # V2 파일 기반 투두 + lockfile
  ├── toolsearch-시스템.md               # always-load / deferred / 메타도구
  ├── 에이전트-개발-인사이트_cc질의.md   # "안 만들기" 철학
  ├── 에이전트-개발-인사이트_cc분석.md   # 도구 description 6패턴
  ├── 에이전트-개발-인사이트_cc기타.md   # 보조 분석
  ├── 도구-실행-10단계-파이프라인.md     # 위와 동일
  ├── multiTurn-flow.html                # 멀티턴 플로우 다이어그램
  ├── 프로덕션_레벨의_Agentic_AI.pdf     # 외부 자료
  ├── system_info/
  │   ├── query-context-management.md    # 5단계 컨텍스트 압축 파이프라인
  │   └── prompts/                       # 시스템 프롬프트 20섹션 + 모델 오버라이드
  ├── tools_info/
  │   ├── toolcalling-loop-prevention.md # 7겹 루프 종료 방어선
  │   ├── toolcalling-performance.md     # 스트리밍 도중 도구 실행 · 투기적 분류기
  │   └── tools_detail/                  # 도구별 상세 명세 (40+)
  ├── cc-analysis/
  │   ├── 00-OVERVIEW.md                 # 4계층 아키텍처 종합
  │   ├── 04-src-core.md                 # 코어 모듈 분석
  │   ├── 05-tools-commands.md           # 도구·명령어 · 스킬·슬래시
  │   ├── 06-src-utils.md                # hooks · thinking · effort · telemetry
  │   ├── 07-components-hooks.md         # React/Ink TUI (참고만)
  │   ├── 08-bridge-services-skills-state.md  # 원격 제어 API · MCP 클라이언트
  │   ├── 09-loadMemoryPrompt-analysis.md  # CLAUDE.md 메모리 시스템
  │   └── 17-getAntModelOverrideSection-analysis.md  # 모델 버전별 교정
  └── src/                               # ✅ 구현 단계 필수 참조 (TS ground truth)
  ```

- 각 Phase 헤더의 `> **참조**:` 라인이 위 자료의 어느 문서를 베이스로 삼는지 명시한다.
- **`/execute-plan` 진입 시 룰**: 해당 Phase 가 다루는 컴포넌트/패턴에 대해 (1) 관련 분석 .md 다시 읽고 의도·이유 확인 → (2) `CC/src/` 에서 grep·glob 으로 실제 구현 위치 식별 → (3) 시그니처·검증 패턴 참고해 파이썬으로 옮긴다. **md 와 src 를 함께 본다** — md 는 "왜" 와 "추상", src 는 "어떻게" 와 "디테일". (100% 복제 X — 백엔드 어휘로 변환, 단 시그니처/네이밍 의도는 보존.)
- 자료가 갱신되면 `js-super:change-propagation` 으로 영향받는 Phase 의 항목을 cascade.

---

## 🧭 설계 원칙 (모든 Phase에 관통)

CC 분석 문서에서 반복적으로 확인된 5가지 핵심 컨셉. 모든 모듈이 이 원칙을 만족하는지 매 Phase 끝에 점검.

1. **정적/동적 분리 (Caching Boundary)** — 시스템 프롬프트·메시지 어디든 정적 부분은 캐시, 동적 부분은 매 턴 재계산. KV 캐시 적중률이 비용·지연의 핵심.
2. **"안 만들기" 원칙** — 분류기, 라우터, 상태머신 만들지 말 것. 도구 description과 시스템 프롬프트가 분류 역할을 한다.
3. **조용한 정규화 (Silent Normalization)** — 도구 입력 백필·정규화는 모델/사용자가 모르게 코드 레벨에서만.
4. **3그룹/3레이어 병렬 분담** — 어태치먼트 수집(3그룹 `asyncio.gather`), 도구 설계(L1 공통규칙 / L2 description / L3 검증), 권한 판정(allow/ask/deny 3단계).
5. **관찰→교정→재관찰** — 모델 실패 패턴은 `@[MODEL: <model> <yyyy-mm>]` 마커로 description·프롬프트에 기록·축적. 마커 자동 수집기로 회귀 추적. 프롬프트는 살아있는 튜닝 결과물.
6. **에러는 모델 피드백** — 도구 실패를 throw 하지 않는다. `{ok: false, error, hint, retryable}` envelope 로 반환 → 모델이 다음 행동을 결정. 재시도/백오프는 루프 책임, 도구 자체는 멱등하게.
7. **격리된 컨텍스트 (Subagent Isolation)** — 무거운 탐색·다중 후보 평가는 서브에이전트로 격리. 메인 컨텍스트엔 결과만 들어옴. mainThread/subThread 어태치먼트 차등 적용.
8. **교체·확장 가능성 (Swappable & Extensible)** — 베이스가 제공하는 건 **인터페이스 + 디스패처 + 참조 구현 1개**. 도메인-특화 본체(분류기·collector·도구·메모리 백엔드 등)는 항상 **갈아끼울 수 있는 슬롯**으로. 모든 디스패처는 `register()` 패턴 — 도메인이 새 구현을 정의하고 등록만 하면 베이스 코드 0줄 수정 없이 동작 (Open/Closed). 베이스가 제공한 참조 구현은 등록 안 하면 그만 + 완전히 제거 가능. 베이스 안에 도메인 가정을 박지 않는다 (예: 코드 도메인 가정 금지).

---

## 📖 산출물 룰 — 각 Phase 끝마다 **인터페이스 개발문서 + 데모 노트북** 두 산출물

> Phase 종료(finishing-a-development-branch) 직전, 베이스를 사용할 도메인 프로젝트가 **공식 라이브러리 docs (pydantic / fastapi 등) 처럼 참조** 할 수 있는 (1) 인터페이스 가이드 + (2) 실행 가능한 데모 노트북 두 산출물을 반드시 같이 낸다. 14 Phase 누적 → 한 권의 공식 매뉴얼 + 한 묶음의 실습 노트북.

**산출물 1: 인터페이스 가이드 (Markdown)**

**위치**: `docs/interfaces/phase-<N>-<slug>.md` (예: `docs/interfaces/phase-1-prompts.md`)

**필수 섹션 순서** (외부 공개 가능성 고려해서 사용 예시가 항상 가장 위, 전체 시그니처는 reference 로 맨 아래):

1. **모듈 책임** — 한 줄. "이 모듈은 무엇을 하는가."
2. **사용 예시** — 도메인 입장에서 가장 흔한 use case 1-4개. 복붙 가능한 완성 코드 우선. (가장 먼저 보이도록.)
3. **핵심 개념** — 도표/다이어그램 (ASCII art 또는 mermaid). 데이터 흐름·의존성·계약.
4. **확장 포인트** — `register()` / override / Protocol 시그니처. "이렇게 갈아끼우세요" 가이드 + 금지 사항.
5. **위험·주의사항** — `<slug>-tech-design.md §6` 의 R-N 중 도메인 사용자가 알아야 할 것 (race·breaking·perf·side-effect). 내부용 R-N id 는 그대로 노출 OK.
6. **다른 모듈과의 연계** — 이 인터페이스가 다른 모듈에서 어떻게 확장·소비되는지. **Phase 번호 사용 금지** — 외부 reader 는 Phase 번호 의미 모름. 반드시 **기능 명칭** (예: "캐시 메트릭", "도구 시스템", "Hooks 시스템", "API 노출 (FastAPI)") 으로 표현.
7. **데모 노트북 / 참조 코드** — `notebooks/phase-<N>-*.ipynb` 또는 `examples/` + `tests/test_*.py` 링크.
8. **Public API (Reference)** — import 가능 심볼 전체 시그니처 (함수·클래스·상수). 코드 블록으로. 위 §2 사용 예시로 감 잡은 후 reference 용도. import 룰 (D-13 / 풀 경로) 도 같이.

**문서 본문에 두지 않는 것**:
- 변경이력 섹션 (인터페이스 문서엔 두지 않음 — 변경 추적은 `docs/features/<date>-<slug>/<slug>-implementation-plan.md` 의 `## 변경이력` 에서)
- 내부 결정 ID (D1-N) 의 풀 설명 — 짧게 참조만 (`(D-13)` 등) OK, 상세는 tech-design 에 둠

**산출 시점**: 9 task 완료 + final code review APPROVED 시점, change-history `[코드-수정]` 직후, `finishing-a-development-branch` 진입 직전.

**산출물 2: 데모 노트북 (Jupyter)**

**위치**: `notebooks/phase-<N>-<slug>-demo.ipynb` (예: `notebooks/phase-1-prompts-demo.ipynb`, `notebooks/phase-2-llm-client-demo.ipynb`)

**필수 셀 구조** (인터페이스 가이드 §사용 예시를 실행 가능한 형태로 + 학습 친화적 4부 골격):

1. **Setup 셀** — `sys.path` patch (`uv` 가 정식 ipykernel 등록 전까지 임시) + import 한 묶음 + `.env` 로딩 안내
2. **1부: 베이스 사용 흐름** — 인터페이스 가이드 §사용 예시 의 가장 기본 use case 1-2개를 마크다운 설명 + 실행 가능 셀로
3. **2부: override / register 슬롯** — `register()` / Protocol 구현 / 도메인 어댑터 끼우기 패턴 (Open/Closed 시연)
4. **3부: escape hatch / 동적부 / 위험 가드** — `dangerous_uncached` 같은 escape hatch + 동적 컴포넌트 주입 + R-N 가드 발동 시나리오 (예: ValueError 가 잘 잡히는지)
5. **Cleanup 셀** — registry / metrics 등 격리 위해 snapshot/restore (단 conftest autouse fixture 와 충돌 안 나게)
6. **다른 모듈 연계 + 실습 4개** — Phase 번호 사용 금지 (인터페이스 가이드와 동일 룰), 기능 명칭으로만. 실습 = 사용자가 빈 셀 채워가며 학습할 수 있는 4 문항 ("X 를 ... 로 바꿔보세요", "Y observer 등록해보세요" 등)

**노트북 주의사항**:
- 사용자가 직접 노트북 셀을 한국어로 수정·주석 추가하는 경우 있음 — 메인이 NotebookEdit 으로 셀 추가/대체할 때 사용자 직접 수정 보존. Write 로 전체 덮어쓰기 금지.
- ipykernel 정식 등록 권장 (`uv add --dev jupyter ipykernel && uv run python -m ipykernel install --user --name best-agent-base`) — 단 deps 추가는 사용자 승인 필요. 임시는 setup 셀의 `sys.path` patch 로 충분.
- 노트북 ruff 잔여는 `notebooks/` 트리 전용 그루밍 — Phase 작업 외 별도 commit 권장 (Phase 1 demo 의 ruff 9 errors 가 그 예).

**적용 범위**: Phase 1 부터 본격 적용 (`notebooks/phase-1-prompts-demo.ipynb` 16 cells). Phase 0 (이미 완료) 는 시간 날 때 backfill (인터페이스 가이드 + 노트북 둘 다).

**검증**: 다음 Phase 진입 시 직전 Phase 의 (1) 인터페이스 문서 + (2) 데모 노트북 둘 다 존재하는지 확인. 둘 중 하나라도 없으면 진입 전에 만들기.

---

## 🏗️ Phase 0 — 프로젝트 골격 & 폴더 구조 설계  ✅ 완료 (tag `phase-0-skeleton-done`)

> **목적**: 빈 껍데기 + 모듈 트리 + 의존 정리. 코드 본체는 다음 Phase부터.
> **결과**: 13/13 AC GREEN, 17 단위 테스트 통과, ruff clean, Docker postgres+redis healthy.
> **산출물**: `docs/features/2026-05-03-phase-0-skeleton/` (PRD + tech-design + impl-plan)

- [x] 폴더 구조 합의 — Flat 9-package layout 채택 (D-9). Phase 0 종료 시점의 실제 트리:
  ```
  best_agent_base/
  ├── __init__.py            # docstring only (D-13)
  ├── config.py              # pydantic-settings Settings 진입점 (✓ 본체)
  ├── core/__init__.py       # 하네스 · 세션 · ReAct 루프 (Phase 5)
  ├── prompts/__init__.py    # 시스템 프롬프트 정적/동적 분리 (Phase 1)
  ├── attachments/__init__.py # 이중 어태치먼트 시스템 (Phase 3)
  ├── tools/__init__.py      # Tool base, registry, search, builtins (Phase 4, 6)
  ├── hitl/__init__.py       # human-in-the-loop (Phase 8)
  ├── llm/                   # 모델 어댑터
  │   ├── __init__.py        # docstring only
  │   ├── models.py          # ✓ GeminiModel(StrEnum) — 모델 ID 카탈로그
  │   ├── profiles.py        # ✓ ModelProfile(BaseModel, frozen) + 베이스 프리셋
  │   └── gemini.py          # ✓ get_gemini(profile) 팩토리 (lazy 인스턴스화)
  ├── context/__init__.py    # 컨텍스트 관리·캐시·블롭 Protocol (Phase 9)
  ├── api/__init__.py        # FastAPI 엔드포인트 (Phase 14)
  └── db/__init__.py         # SQLAlchemy 모델 · Tier 2 영속 (Phase 9·11·14)

  tests/
  ├── __init__.py
  ├── test_smoke.py          # ✓ 11 cases — 9 서브패키지 + config import 무결성
  ├── test_settings.py       # ✓ 6 cases — Settings 우선순위 + lazy 룰 (D-12)
  └── test_llm_profiles.py   # ✓ 12 cases — 모델/프로파일 카탈로그 검증 (raw string 거부)

  scripts/
  ├── __init__.py
  └── change_id.py           # ✓ js-super:change-history 헬퍼 (CH-id 생성)

  docs/
  ├── local-dev-setup.md             # ✓ docker-compose 사용 가이드
  └── features/2026-05-03-phase-0-skeleton/
      ├── phase-0-skeleton-requirements.md   # ✓ PRD
      ├── phase-0-skeleton-tech-design.md    # ✓ 개발방향
      └── phase-0-skeleton-implementation-plan.md  # ✓ 구현계획서

  # 루트
  docker-compose.yml         # ✓ postgres host 5435 + redis 6379 + healthchecks
  .env.example               # ✓ GOOGLE_API_KEY/DATABASE_URL/REDIS_URL/BLOB_STORE_URL/...
  pyproject.toml             # ✓ deps + [tool.ruff] + [tool.pytest.ini_options]
  uv.lock                    # ✓ 결정성 보장 (NFR-1)
  main.py                    # ✓ LangGraph 단일 노드 데모 (Settings 마이그레이션은 Phase 1+ 그루밍)
  README.md                  # ✓ Setup 4 단계 + 🟢 Phase 0 완료 상태
  TODO.md                    # 이 문서
  .python-version, .gitignore, .vscode/  # 기타 루트 파일
  ```
  > 각 서브패키지의 본체 파일(`session.py`, `react_loop.py`, `boundary.py` 등)은 해당 Phase 에서 생성. Phase 0 시점에는 빈 `__init__.py` (한 줄 docstring) 만 박음 (D-13). **예외**: `llm/` 은 Phase 0 후속 보강(`1e5914a`) 으로 모델 카탈로그(`models.py`) + 프로파일(`profiles.py`) + 팩토리(`gemini.py`) 본체가 들어감 — 도메인 교체 가능 슬롯 (원칙 #8).
- [x] 의존성 추가 — `fastapi uvicorn sqlalchemy[asyncio] asyncpg alembic pydantic-settings tiktoken` (런타임) + `pytest pytest-asyncio ruff aiosqlite` (dev)
- [x] 디렉토리·`__init__.py` 빈 껍데기로 생성, import 경로 검증 — 9 서브패키지 + smoke 테스트 11 cases
- [x] `pyproject.toml`에 `tool.ruff`, `tool.pytest` 최소 설정 — line-length=100, py312, E/F/I + testpaths/asyncio_mode=auto
- [x] 환경 변수 로딩 일원화 (`pydantic-settings` 기반 `Settings`) — 6 필드 (google_api_key 필수 + log_level/database_url/agent_state_dir 디폴트 + redis_url/blob_store_url Optional), lazy 인스턴스화 (D-12)
- [x] **추가**: 로컬 dev 인프라 (`docker-compose.yml` — postgres host **5435** + redis 6379 + healthchecks) — D-11
- [x] **추가**: `docs/local-dev-setup.md` — Docker 사용 가이드
- [x] **추가**: `scripts/change_id.py` — js-super:change-history 헬퍼

**Phase 1+ 그루밍 노트** (final code review 도출, 각 Phase 진입 시 처리):
1. README Status 라벨 갱신 (이미 처리됨 → 🟢 Phase 0 완료)
2. `main.py` 의 `load_dotenv()` 직접 호출 → `Settings()` 진입점으로 마이그레이션
3. `tests/conftest.py` 도입 (Phase 1+ 부터 공통 async fixture 필요 시)
4. `Settings.log_level` 을 `Literal[DEBUG, INFO, WARNING, ERROR, CRITICAL]` 로 강화 (Phase 11 Hooks 시점)
5. `Settings.agent_state_dir` 을 `Path` 로 정규화 (Phase 9 캐시/블롭 본체에서)
6. `extra="ignore"` → `extra="forbid"` 전환 검토 (Phase 11 Settings 시스템 확장 시)

---

## 🧱 Phase 1 — 시스템 프롬프트 기법 (정적/동적 분리)  ✅ 완료 (main `1a0231e` 머지, 70/70 tests)

> **산출물**: `docs/features/2026-05-03-phase-1-prompts/` (PRD + tech-design + impl-plan, CH-001..004) / `docs/interfaces/phase-1-prompts.md` (공식 인터페이스 가이드) / `notebooks/phase-1-prompts-demo.ipynb` (데모)
> **결과**: 9 task subagent-driven 완료, 41 신규 tests (29 → 70), final code review APPROVED, ruff clean

> **참조 (필수)**:
> - `prompt-engineering-techniques.md` — 정적/동적 경계 마커 메커니즘
> - `에이전트-성능-결정요인-총정리.md` — 14 프롬프트 기법 + 캐시 분리
> - **`시스템프롬프트-7섹션-요약.md`** — **7 섹션 각각의 주제·핵심 내용·역할 (헤딩 골격 설계 시 1차 자료)**
>
> **도메인 중립성 (필수)**: 본 베이스의 7 섹션 골격은 **어떤 도메인 에이전트에서도 그대로 쓸 수 있게** 설계. CC 의 7 섹션은 코딩 도메인용 콘텐츠로 채워져 있지만 — 우리 베이스는 **섹션 슬롯과 정적/동적 경계만 제공**, 콘텐츠는 도메인 프로젝트가 register/주입 (원칙 #8 Open/Closed 적용). 코딩 어휘를 베이스에 박지 않는다.

### 7 섹션 골격 (참조 자료의 의미 정리)

| # | 섹션 | 주제 | 베이스 슬롯 책임 |
|---|---|---|---|
| 1 | **Intro** | 정체성 + 보안 가드 ("너는 누구") | 빈 슬롯 — 도메인이 채움 (CC: 코딩 에이전트 / 의료: 의료 보조 / 금융: 거래 보조 등) |
| 2 | **System** | 도구·UI·시스템 작동 규칙 (메타 환경) | 베이스 공통 룰만 (system-reminder 태그, prompt injection 경고, 컨텍스트 압축 안내) — 도메인 부가 룰 추가 가능 |
| 3 | **Doing tasks** | 작업 철학 (가장 김; CC 는 코딩 철학) | **빈 슬롯** — 도메인이 채움. `@[MODEL: ...]` 마커 누적 영역 (원칙 #5) |
| 4 | **Executing actions with care** | 위험 작업 가드 (가역성/blast radius) | 베이스 공통 가드 골격 (4 카테고리: 파괴적/되돌리기 어려움/공유 영향/3rd-party) — 도메인이 카테고리 확장 |
| 5 | **Using your tools** | 도구 선택 규칙 (전용 도구 우선, 병렬/순차) | 베이스가 도구 메타데이터(`is_readonly`)로 자동 안내 — 도메인은 도구 개별 description 만 |
| 6 | **Tone and style** | 응답 표기 규칙 (말투, 형식) | 베이스 디폴트 (이모지/file_path 형식 등) — 도메인이 override 가능 |
| 7 | **Output efficiency** | 출력 양·우선순위 (액션 먼저, inverted pyramid) | 베이스 공통 디폴트 + audience 프로파일 hook (외부/내부/엔드유저 등) |

### 작업 항목

- [x] **Section Protocol** — `PromptSection(Protocol, runtime_checkable)` 7 섹션 인스턴스 (`prompts/sections.py`)
- [x] 7 섹션 골격 + 도메인-중립 default 텍스트 (`prompts/sections.py` 의 `_BaseSection` + `BASE_SECTIONS` 튜플)
- [x] `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커 + R-5 충돌 가드 (`prompts/boundary.py` + `prompts/render.py`)
- [x] `dangerous_uncached(*, name, content, reason)` 헬퍼 + `DangerousUncached(BaseModel frozen, reason min_length=1)` (R-4 mitigation)
- [x] 정적 섹션은 `BASE_SECTIONS` 순회·동적은 `static=False` 분류 (`_render_static`/`_render_dynamic` 분리)
- [x] `get_static_hash(ctx) → sha256[:16]` 캐시 측정 슬롯 (`prompts/render.py`)
- [x] **render(ctx) → str** — 정적 7섹션 + BOUNDARY + 동적부 조립 (`prompts/render.py`)
- [x] **`SectionRegistry` + `registry.register(name, section)` API** — 베이스 0줄 수정 override (D-8) (`prompts/registry.py`)
- [x] 단위 테스트 8 파일 41건:
  - `test_prompts_sections.py` (Protocol/이름/static/render)
  - `test_prompts_static_stability.py` (해시 N=10 동일)
  - `test_prompts_render.py` (동적 변동 허용)
  - `test_prompts_registry.py` (register/override 격리)
  - `test_prompts_dangerous_uncached.py` / `test_prompts_cache_slot.py` / `test_no_domain_vocab.py` / `test_init_purity.py`
- [x] **공식 인터페이스 가이드** `docs/interfaces/phase-1-prompts.md` (산출물 룰 첫 적용)
- [x] **데모 노트북** `notebooks/phase-1-prompts-demo.ipynb`

---

## 🧊 Phase 2 — LLM 클라이언트 통합 (캐싱 흡수)  ✅ 완료 (main `21b27f5` 머지, 111/111 tests)

> **산출물**: `docs/features/2026-05-03-phase-2-llm-client/` (PRD + tech-design + impl-plan, CH-001..017) / `docs/interfaces/phase-2-llm-client.md` (공식 인터페이스 가이드) / `notebooks/phase-2-llm-client-demo.ipynb` (데모, 산출물 룰 4부 골격)
> **결과**: 9 task + Anthropic FR-7 cascade 완료, 41 신규 tests (70 → 111), final code review APPROVED, ruff clean (Phase 2 scope)
> **사용자 결정 (CH-010/011/012)**: 본래 OOS-1 ("Anthropic 어댑터 본 구현") 였던 항목을 본 Phase 범위에 포함. 이유 = provider 추상화 검증의 진정한 완성은 2개 어댑터 동시 구현으로 가능 (Gemini `CachedContent` ↔ Anthropic `cache_control` ephemeral marker 두 메커니즘이 동일 `LLMClient` + `CachePolicy` 흐름으로 흡수 실증).

> **목적** (원본): 모델 호출 어댑터를 베이스화. Provider 메커니즘(Gemini `CachedContent` / Anthropic `cache_control`) 차이를 **호출 레이어가 생기는 이 시점에** 정확히 모델링. Phase 1 의 정적/동적 분리 슬롯 위에 실제 호출 레이어를 얹는다.
>
> **결정 (2026-05-03)**: 본래 "Phase 2 — KV 캐싱(프롬프트 캐싱) 적용" 으로 분리돼 있던 항목을 **LLM 클라이언트 Phase 에 흡수**. 이유:
> - **D-2 "안 만들기" 위반 회피** — LLM 호출 레이어가 없는 시점에 "캐시 측정·정책 추상" 만 따로 만드는 건 호출자 없는 추상화. Phase 1 의 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커 + `get_static_hash(ctx)` 가 이미 캐시 친화 슬롯 그 자체.
> - **Provider 메커니즘 차이** — Gemini(`CachedContent` 객체 + TTL + 최소 토큰 Flash 1024 / Pro 4096) ↔ Anthropic(`cache_control` 마커) 를 호출 레이어 없이 선추상화하면 **둘 다 어색하게 모델링될 위험**. 두 SDK 의 실제 시그니처를 보면서 한 번에 통합 설계가 정확함.
> - **9 설계원칙 #1 (정적/동적 분리)** 이 이미 횡단 제약. "캐시 친화" 룰을 Phase 별 체크리스트로 따로 둘 필요 없음.

> **참조 (필수)**:
> - Phase 0 의 `best_agent_base/llm/` (Gemini 어댑터 1차 골격 — `models.py` / `profiles.py` / `gemini.py`)
> - `prompt-engineering-techniques.md` — 정적/동적 경계 마커 메커니즘
> - `에이전트-성능-결정요인-총정리.md` — 캐시 적중률과 비용·지연 관계
> - CC `src/services/api.ts` (특히 `splitSysPromptPrefix` 등) — 캐시 송신 패턴 (md + src 둘 다)

### 작업 항목

- [x] `LLMClient` Protocol (B-thin, runtime_checkable) — `async generate(ctx, *, cache_policy=None) → LLMResponse` + `count_tokens` (`best_agent_base/llm/client.py`)
- [x] Gemini 어댑터 참조 구현 — `google.genai` 직접 사용 (LangChain 제거), `GeminiClient` 클래스 (`best_agent_base/llm/gemini.py` 재작성)
- [x] **캐시 통합 (Gemini)** — `CachedContent` 자동 생성/재사용, key=`get_static_hash(ctx)`, `asyncio.Lock` per static_hash (R-1), D6 fallback (캐시 실패 시 None → 호출 우회)
- [x] **Anthropic 어댑터 본 구현** — `AnthropicClient` (`best_agent_base/llm/anthropic.py`), system 메시지 마지막 text block 에 `cache_control: {"type": "ephemeral"}` marker (D7), CH-010 cascade
- [x] **캐시 메트릭 슬롯** — `CacheEvent(StrEnum)` + `CacheObserver` + `CacheMetrics` (`best_agent_base/llm/cache_metrics.py`), HASH_CHANGE 메트릭 계약 명문화 (causal annotation)
- [x] 메시지 빌더 — `build_gemini_messages(ctx)` (`best_agent_base/llm/messages.py`) — provider-agnostic boundary split (Anthropic 도 재사용)
- [x] `CachePolicy` frozen 모델 — enabled / ttl_seconds / force_invalidate (`best_agent_base/llm/cache_policy.py`)
- [x] 통합 테스트 — 동일 ctx 두 번 호출 → 두 번째 cache hit (mock SDK), boundary 위/아래 검증, race 시나리오 (5 동시 호출 → caches.create 1회), cache_control marker 위치 회귀
- [x] `tests/conftest.py` autouse `restore_registry` fixture (그루밍 노트 #3 처리)
- [x] **공식 인터페이스 가이드** `docs/interfaces/phase-2-llm-client.md` (산출물 룰 8섹션)
- [x] **데모 노트북** `notebooks/phase-2-llm-client-demo.ipynb` (산출물 룰 4부 골격)

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

> **참조**: `claude-code-research.md`, `에이전트-개발-인사이트_cc질의.md`, `tools_info/toolcalling-loop-prevention.md`

- [ ] `ReactLoop` — `async while True` + 토큰 임계 도달 / 종료 신호 / 스텝 상한
- [ ] **7겹 루프 종료 방어선** (Protocol 로 정의, 각 게이트 교체 가능)
  - (1) maxTurns / (2) maxBudgetUsd / (3) 컨텍스트 토큰 한계
  - (4) output recovery / (5) 구조화 출력 종료 신호
  - (6) 사용자 인터럽트(HITL) / (7) Stop 훅
- [ ] 읽기 전용 도구 병렬(`asyncio.gather`) / 쓰기 도구 순차 분리 (도구 메타데이터 기반)
- [ ] 도구 호출 순서가 어그러지면 description 패턴 P1·P5에 의지 + 코드 가드(예: Edit 전 Read 강제) 한 줄
- [ ] 흐름을 끊는 도구(`SendUserMessage`, HITL 권한 대기)는 루프에 명시적 yield 포인트
- [ ] FastAPI 스트리밍을 염두에 둔 `async generator` 인터페이스
- [ ] **스트리밍 + thinking 블록**: 모델 응답 청크 단위 처리, thinking 블록 분리 보존, eager input streaming(스트리밍 도중 도구 호출 시작) 인터페이스만 정의

---

## 🔍 Phase 6 — 도구 서치 시스템 (Always-load / Deferred) + MCP 훅

> **참조**: `toolsearch-시스템.md`

- [ ] `ToolRegistry` — 도구를 `always_load` / `deferred` 태그로 분류
- [ ] `ToolSearch` 메타 도구
  - `select:Name1,Name2` 직접 선택
  - 키워드 검색 → 상위 N개 schema 반환
  - 반환 형식은 모델이 곧장 호출 가능하게 (description + parameters 동시)
- [ ] 새 도구 로드 시 `deferred_tools_delta` 어태치먼트 발화
- [ ] 캐시 영향 측정 — deferred 도구가 정적 카탈로그를 깨지 않음을 검증
- [ ] **MCP-style 외부 도구 서버 어댑터** (Protocol 만, 실제 MCP 클라이언트 구현은 후속) — 모든 외부 도구는 deferred 로 등록

---

## 👤 Phase 7 — 유저 질문 어태치먼트 (입력 시점 처리)

> **참조**: `attachment-system.md` 의 userInputAttachments 부분

- [ ] `@path/to/file` → 파일 내용 자동 첨부
- [ ] `@db:table.row_id` 같은 백엔드 특화 멘션 (FastAPI/SQLAlchemy 컨텍스트)
- [ ] 첨부 추출 후 메시지에서 토큰 짤림 방지 (원본 보존 + system-reminder로 부가)
- [ ] 입력 검증 — 권한 없는 리소스 멘션은 거부 또는 마스킹

---

## ✋ Phase 8 — 휴먼 인 더 루프 (권한 + 비동기 대기 + 투기적 분류기)

> **참조**: `human-in-the-loop.md`, `tools_info/toolcalling-performance.md`

- [ ] `Permission` — 3단계 판정 (deny / ask / allow), 모드(default / acceptEdits / bypass / dontAsk / auto)
- [ ] `asyncio.Event` 기반 `Waiter` (Promise + resolve의 파이썬 등가)
- [ ] `resolve_once` 보장 (이중 응답 방어)
- [ ] FastAPI 측: 별도 `/permissions/{request_id}/respond` 엔드포인트로 외부 응답 수신 → Waiter 해제
- [ ] auto 모드: 연속 N회 거부 시 자동 해제 정책
- [ ] **투기적 분류기 (Speculative Classifier)** — 권한 판정용 LLM 분류기를 `asyncio.create_task()` 로 스트리밍과 병렬 실행. 도구 호출이 실제로 들어왔을 때 await → 대기시간 0에 가깝게.

---

## 🧹 Phase 9 — 컨텍스트 관리 (5단계 압축 파이프라인 / 파일시스템 / 인수인계)

> **참조**: `에이전트-개발-인사이트_cc분석.md`, `claude-code-research.md`, `system_info/query-context-management.md`

- [ ] **5단계 컨텍스트 압축 파이프라인** (각 단계 Strategy Protocol, 임계값 설정 가능)
  1. `applyToolResultBudget` — 큰 도구 결과를 사이즈 가드 (truncate + 요약 핸들)
  2. `snipCompact` — 오래된 보조 메시지 잘라내기 ⚠️
  3. `microcompact` — 인접 메시지 묶음을 로컬 요약으로 치환
  4. `contextCollapse` — 중복/유사 컨텍스트 합치기 ⚠️
  5. `autocompact` — 토큰 임계 초과 시 전체 대화 요약 → 시스템 메시지 주입

  > ⚠️ **`snipCompact`, `contextCollapse` 는 CC src 에 TS 본체 비공개** (`.js` 로만 `require()` 됨). 구현 시 `system_info/query-context-management.md` 의 발동 조건·Before/After 예시 기반으로 **알고리즘을 우리가 직접 설계**. 나머지 3개(applyToolResultBudget / microCompact / autoCompact)는 src 참조 가능.
- [ ] 토큰 카운터 (`tiktoken` 또는 모델 자체 카운터) — 모델별 어댑터
- [ ] 큰 결과 원본은 파일시스템(또는 DB BLOB) 에 저장 후 핸들 반환
- [ ] 파일시스템 응용 — 외부 메모리(`./.agent_state/`)에 장기 컨텍스트 저장·읽기
- [ ] 인수인계 (`/handoff` 등가) — 다음 세션이 그대로 받을 수 있는 핸드오프 문서 자동 생성 (9섹션 골격)
- [ ] DB(SQLAlchemy)에 세션·턴·도구호출 영속화 (재현·디버깅용) — **멀티턴 대화 레저** 스키마 확정

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

## 🪢 Phase 11 — Hooks & Settings 시스템 (확장 포인트)

> **참조**: `cc-analysis/06-src-utils.md`, `tools_info/toolcalling-loop-prevention.md`

- [ ] `Hook` Protocol — 동기·비동기, 우선순위, 단락 가능 (`return False` → 다음 단계 skip)
- [ ] 표준 훅 포인트 (이름·시점만 정의, 구현은 후속)
  - `UserPromptSubmit` — 유저 입력 직후
  - `PreToolUse` / `PostToolUse` — 도구 실행 전·후
  - `PreModelCall` / `PostModelCall` — 모델 호출 전·후
  - `Stop` — 루프 종료 직전
  - `SessionStart` / `SessionEnd`
- [ ] `AsyncHookRegistry` — 등록/해지/순회, 사용자 정의 훅 동적 추가
- [ ] 파일 변경 워처 (`fileChangedWatcher` 등가) 인터페이스만
- [ ] **Settings 시스템** — `pydantic-settings` 기반 계층 (env > project config > user config > default), 권한·훅·모델 설정 한 곳에
- [ ] settings 핫 리로드 훅 (선택)

---

## 🤖 Phase 12 — Subagent / Agent 도구 아키텍처

> **참조**: `cc-analysis/05-tools-commands.md`, `08-bridge-services-skills-state.md`, `attachment-system.md` (mainThread vs subagent 차등)

- [ ] `Subagent` Protocol — 격리된 컨텍스트(자체 시스템 프롬프트·자체 도구 셋·자체 토큰 예산), 결과만 메인으로 반환
- [ ] `AgentTool` 빌트인 — 메인 에이전트가 호출하는 dispatch 도구 (`subagent_type`, `prompt`, `run_in_background`)
- [ ] **차등 어태치먼트** — `mainThreadAttachments` 는 서브엔 안 들어감 (이미 Phase 3 에서 구분됐지만 여기서 강제 검증)
- [ ] 결과 집계기 (`ResultAggregator`) — 여러 서브에이전트 병렬 실행 + 결과 합치기 인터페이스
- [ ] 서브에이전트 카탈로그 (`registry.py`) — 이름 → (system prompt, allowed tools, model) 매핑
- [ ] 서브 → 메인 텔레메트리 전파 (토큰·비용·실패 사유)
- [ ] 백그라운드 실행 어댑터 (FastAPI `BackgroundTasks` 또는 task queue 추상)

---

## 🧠 Phase 13 — Memory 시스템 (4타입 영속 컨텍스트)

> **참조**: `cc-analysis/09-loadMemoryPrompt-analysis.md`, 사용자 글로벌 `~/.claude/CLAUDE.md` 패턴

- [ ] `Memory` Protocol — `read()` / `write()` / `search()` / `forget()`, 백엔드 교체 가능 (file / SQLAlchemy / vector store)
- [ ] **4 타입 분리** (CC 의 user / feedback / project / reference 패턴)
  - `user` — 사용자 프로필·선호·역할
  - `feedback` — 교정 지시 (rule + Why + How to apply)
  - `project` — 프로젝트 상태·결정·기한
  - `reference` — 외부 시스템 포인터
- [ ] **MEMORY.md 인덱스 패턴** — 메인 컨텍스트엔 인덱스 한 줄씩, 본문은 lazy 로드
- [ ] **Auto-memory 훅** — 사용자 발화에서 메모리 후보 감지 → 자동 저장 (PreModelCall 훅 활용)
- [ ] DB-backed 구현 (SQLAlchemy) — 세션 간 영속, project_id 스코프
- [ ] CLI/MCP 호환을 위한 파일 어댑터도 병행

---

## 🌐 Phase 14 — FastAPI 노출 (베이스 API)

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
- [ ] 새 프로젝트가 `from best_agent_base import ReactLoop, ToolRegistry, HookRegistry, Memory, build_app` 한 번으로 시작 가능
- [ ] 정적/동적 분리 → 두 번째 호출 시 캐시 적중 확인
- [ ] HITL 외부 응답으로 도구 실행 재개 확인
- [ ] 도구 서치로 deferred 도구 동적 호출 가능 확인
- [ ] 핸드오프 문서로 다른 세션이 작업 이어받기 가능 확인
- [ ] 서브에이전트 dispatch → 결과만 메인 컨텍스트에 반영 확인 (mainThread 어태치먼트 격리)
- [ ] 훅 등록만으로 모델 호출/도구 호출 흐름이 가로채진다는 것 확인
- [ ] Memory write → 다음 세션 시작 시 read 로 복원 확인
- [ ] **모든 핵심 추상이 Protocol/ABC 로 노출**, 참조 구현 1개씩 + 단위 테스트 — "교체 가능" 검증

---

## 📦 Out of scope (베이스 단계에선 보류, 향후 후속 프로젝트로)

- Skills / Slash command 레지스트리 (CLI-적, 백엔드 베이스 우선순위 낮음)
- 풀 MCP 클라이언트 (Phase 6 에서 어댑터 Protocol 만)
- React/Ink TUI 컴포넌트 (CC 의 프론트엔드 영역)
- GrowthBook 류 피처 플래그 인프라 (텔레메트리 마커는 Phase 5/원칙 5 에서 흡수)
- 분산 task queue (백그라운드 실행은 FastAPI `BackgroundTasks` 어댑터로 시작)

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
- **CC/ 참조 룰**: 설계 단계는 분석 .md 위주, **구현(`/execute-plan`) 진입 시엔 분석 .md + src/ 둘 다 필수 참조** — md 로 의도 재확인, src 로 실제 시그니처·검증 의도 확보 후 파이썬으로 옮긴다.
