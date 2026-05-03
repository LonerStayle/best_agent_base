# 인수인계 문서 — best_agent_base

> **다음 세션이 이 한 파일만 읽어도 즉시 이어갈 수 있게 작성.**
> 마지막 갱신: 2026-05-03 (Phase 1 완료 + 산출물 룰 신설 + 인터페이스 가이드 첫 적용 후)

---

## 🎯 Goal — 프로젝트 최종 목적

**Claude Code(TS·프론트엔드 CLI)의 하네스 기법을 파이썬 백엔드(FastAPI + SQLAlchemy)로 포팅한, 모든 에이전트 프로젝트의 Base 모듈을 만든다.**

- 도메인 무관 — 어떤 에이전트 프로젝트든 `import best_agent_base` 한 번으로 시작.
- **인터페이스·계약 중심 골격** (추상 클래스 / Protocol / Pydantic 스키마 / 엔드포인트 시그니처).
- 다른 프로젝트는 **상속·구현·교체**만 하면 됨 (원칙 #8).
- 14 Phase 로드맵의 마지막은 FastAPI 엔드포인트로 에이전트 노출.
- 사용자 실력 향상도 목적 → **스텝바이스텝**, 한꺼번에 다 짜지 않음.

자세한 마스터 로드맵: [`TODO.md`](./TODO.md)

---

## 📍 Current Progress

### Phase 0 — 프로젝트 골격 ✅ 완료 (tag `phase-0-skeleton-done`, main `94f3b2d`)

- 9 서브패키지 + `__init__.py` docstring-only (D-13)
- `Settings(BaseSettings)` 6 필드, lazy 인스턴스화 (D-12)
- Docker compose (postgres 5435 + redis 6379)
- LLM 카탈로그: `GeminiModel(StrEnum)` + `ModelProfile(frozen)` + 프리셋 (cogito 패턴)
- 29 tests (smoke 11 + settings 6 + llm_profiles 12)

### Phase 1 — 시스템 프롬프트 7섹션 골격 ✅ 완료 (main `1a0231e` 머지)

**산출물 (commits `c75d906` ~ `f5c2b7b`)**:
- `best_agent_base/prompts/` 4 src 파일:
  - `sections.py` — `PromptSection(Protocol, runtime_checkable)` + 7 베이스 인스턴스 (`Intro`/`System`/`DoingTasks`/`ExecutingActions`/`UsingTools`/`ToneStyle`/`OutputEfficiency`) + `BASE_SECTIONS`
  - `boundary.py` — `SYSTEM_PROMPT_DYNAMIC_BOUNDARY = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"` + `DangerousUncached(BaseModel frozen, reason min_length=1)` + `dangerous_uncached(*, name, content, reason)`
  - `registry.py` — `SectionRegistry` + `register/get/all_sections`, 모듈 로딩 시 `BASE_SECTIONS` 7개 자동 register, 싱글톤 `registry` (R-1: register-once-then-read-many)
  - `render.py` — `RenderContext(BaseModel frozen)` + `render(ctx)` + `_render_static`/`_render_dynamic` (R-5 마커 충돌 ValueError 가드) + `get_static_hash(ctx) → sha256[:16]`
- `tests/` — 8 신규 테스트 파일, **41 신규 tests** (29 → 70 total). 모두 GREEN, ruff clean
- `docs/features/2026-05-03-phase-1-prompts/` — PRD + tech-design + impl-plan, change-history CH-001..004
- **`docs/interfaces/phase-1-prompts.md`** — 공식 인터페이스 가이드 (산출물 룰 첫 적용)
- **`notebooks/phase-1-prompts-demo.ipynb`** — 데모 노트북 (16 cells, 1부 베이스 → 2부 override → 3부 escape hatch + 동적 → 4부 R-5 가드 → cleanup → 다른 모듈 연계 + 실습 4개)

### git 상태
- 브랜치: `main` (HEAD `f5c2b7b` 기준 — Phase 1 머지 + TODO 산출물 룰 + 인터페이스 가이드 commit 까지)
- `phase-1-prompts-impl` 브랜치/워크트리 — 머지 후 정리됨
- **사용자의 `.worktrees/병렬구현-테스트` 워크트리는 절대 건드리지 말 것** (사용자 연구용)
- origin (GitHub `LonerStayle/best_agent_base`) — push 안 함
- tag `phase-0-skeleton-done` → `68c91a9` (Phase 1 종료 시 새 tag 미생성)

---

## 🆕 신설 룰 (Phase 1 종료 시 도입)

### 📖 산출물 룰 — 각 Phase 끝마다 인터페이스 개발문서

> 자세한 내용: [`TODO.md` §📖 산출물 룰](./TODO.md#-산출물-룰--각-phase-끝마다-인터페이스-개발문서-남기기)

- **위치**: `docs/interfaces/phase-<N>-<slug>.md`
- **산출 시점**: 9 task 완료 + final review APPROVED + change-history `[코드-수정]` 직후, finishing-branch 직전
- **외부 공개 룰** (중요): 다른 모듈 연계 시 **Phase 번호 사용 금지** — 외부 reader 가 의미 모름. **기능 명칭** ("캐시 메트릭", "도구 시스템", "Hooks 시스템", "API 노출") 으로 표현
- **섹션 순서** (외부 공개 가독성 우선):
  1. 모듈 책임 (한 줄)
  2. **사용 예시** ← 가장 위
  3. 핵심 개념 (도표)
  4. 확장 포인트 (+ 금지 사항)
  5. 위험·주의사항 (R-N)
  6. 다른 모듈과의 연계 (기능명만)
  7. 데모 노트북 / 참조 코드
  8. **Public API (Reference)** ← 맨 아래
- **변경이력 섹션 두지 않음** (변경 추적은 `docs/features/<date>-<slug>/<slug>-implementation-plan.md`)
- **검증**: 다음 Phase 진입 시 직전 Phase 의 인터페이스 문서 존재 여부 확인. 없으면 진입 전 작성

---

## ✅ What Worked

- **`js-super` 풀 사이클** (brainstorm → design → write-plan → execute-plan → finishing) — Phase 0/1 두 번 모두 깨끗 완성. 매 단계 게이트(verify-spec, change-history, 단일 승인)가 정합성 보장.
- **Subagent-driven-development** — Phase 1 에서 9 implementer + 9 reviewer (spec+quality 9 task) + 1 final = 19회 dispatch. 메인 컨텍스트 절약 (50% 사용 시점에 인수인계 1회만 했음). Task 1·4 만 reviewer Important 발견 → 메인이 직접 fix → 나머지는 nit-only PASS.
- **TDD RED → GREEN 사이클** — 9 task 모두 test-first. Task 6/7/8 (test-only) 도 동일 패턴.
- **Worktree-per-Phase 패턴** — `.worktrees/<phase-name>-impl` 에서 작업 → main 머지 → 정리. main 깨끗 유지. **doc 작업은 main 직접, 코드 구현 단계만 worktree** (사용자 룰).
- **change-history cross-link** — Phase 1: CH-001 PRD → CH-002 design → CH-003 plan → CH-004 코드 (모두 cross-link).
- **인터페이스 가이드 산출물 룰 신설** — 도메인 프로젝트가 공식 라이브러리 docs 처럼 reference 가능. 누적 14 Phase → 한 권의 공식 매뉴얼.

---

## ❌ What Didn't Work / 주의

- **Write 가 사용자 직접 노트북 수정을 덮어씀** — 사용자가 Jupyter 에서 노트북 cell 을 한국어로 수정 (예: `# 작업순서`, `타입힌트를 사용할 수 있다.`) 한 후 메인이 Write 로 친절한 버전 덮어씀. 다음에 노트북/사용자 직접 수정 가능한 파일 다룰 때는 **변경 사항 확인 후 보존**, 또는 NotebookEdit 으로 추가/대체만.
- **노트북 setup 셀 필요** — Jupyter 커널이 .venv 가 아니면 ModuleNotFoundError. setup 셀에 sys.path patch 박아두면 안전. 더 견고하려면 `uv add --dev jupyter ipykernel && uv run python -m ipykernel install --user --name best-agent-base` 권장.
- **D-13 위반은 후속 발견 가능** — Phase 0 T6 reviewer 가 한번 발견. Phase 1 에선 `tests/test_init_purity.py` AST 검증으로 자동화. 후속 Phase 신규 추상 추가 시 `__init__.py` docstring-only 룰 자동 검증됨.
- **`extra="ignore"` 문제** — pydantic-settings typo silent ignore. Phase 11 Hooks 시점에 `extra="forbid"` 전환 검토 (그루밍 노트).
- **사용자 글로벌 CLAUDE.md 룰**: "탐색/플래닝 → 서브에이전트, 실행 → 메인" — Phase 0/1 모두 사용자가 명시적으로 subagent-driven 선택. 다음 Phase 부터 디폴트 = 메인 실행, subagent-driven 은 사용자 명시 시에만.
- **CC `src/contextCollapse/` 와 `src/services/compact/snipCompact.js`** — TS 본체 비공개 (.js only). Phase 9 (컨텍스트 관리) 구현 시 `system_info/query-context-management.md` 의 발동 조건/Before-After 만으로 알고리즘 직접 설계 필요.

---

## 🔧 핵심 설계 원칙 (8가지, 모든 Phase 관통)

> [`TODO.md` §🧭 설계 원칙](./TODO.md#-설계-원칙-모든-phase에-관통) 참조

1. 정적/동적 분리 (Caching Boundary) — Phase 1 에서 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커로 본격 구현됨
2. "안 만들기" 원칙
3. 조용한 정규화
4. 3그룹/3레이어 병렬 분담
5. 관찰→교정→재관찰 (`@[MODEL: ...]` 마커)
6. 에러는 모델 피드백 (envelope 반환)
7. 격리된 컨텍스트 (Subagent Isolation)
8. **교체·확장 가능성** — Phase 1 의 `SectionRegistry.register()` 가 첫 적용 사례. 모든 후속 Phase 도 동일 패턴

---

## 📚 참조 베이스 (Source of Truth)

- 루트: `/Users/goldenplanet/jinsup_space/CC/`
- 분석 .md 들 + `system_info/` + `tools_info/` + `cc-analysis/` + `src/`
- **구현 진입 시 룰**: 관련 분석 .md 다시 읽기 → `CC/src/` grep·glob → 시그니처/검증 패턴 참고해 파이썬으로 옮김. **md=의도, src=ground truth — 둘 다 본다**.
- 자세한 트리: [`TODO.md` §📚 참조 베이스](./TODO.md#-참조-베이스-source-of-truth)

---

## 🛤️ Next Steps — Phase 2 시작 권장

> **다음 세션이 사용자에게 "Phase 2 가자" 신호 받으면 아래 흐름:**

### Phase 2 — LLM 클라이언트 통합 (캐싱 흡수)

> [`TODO.md` §🧊 Phase 2](./TODO.md#-phase-2--llm-클라이언트-통합-캐싱-흡수) 참조

**결정 (2026-05-03)**: 본래 "Phase 2 — KV 캐싱(프롬프트 캐싱)" 으로 분리됐던 항목은 LLM 클라이언트 Phase 에 흡수. 이유 3가지:
1. **D-2 "안 만들기"** — LLM 호출 레이어 없는 시점에 캐시 측정 인프라만 만드는 건 호출자 없는 추상화. Phase 1 boundary 마커 + `get_static_hash` 가 이미 캐시 친화 슬롯.
2. **Provider 메커니즘 차이** — Gemini(`CachedContent` 객체 + TTL) ↔ Anthropic(`cache_control` 마커) 를 호출 레이어 없이 미리 추상화하면 둘 다 어색하게 모델링될 위험. 실제 SDK 시그니처 보면서 한 번에 통합 설계.
3. **9 설계원칙 #1 (정적/동적 분리)** 가 이미 횡단 제약. 별도 Phase 룰 추가 불필요.

**핵심**: Phase 0 의 `best_agent_base/llm/` 1차 골격(`models.py`/`profiles.py`/`gemini.py`) 위에 `LLMClient` Protocol + Gemini 어댑터 본체 + Gemini `CachedContent` 통합 + 캐시 메트릭 슬롯 + Phase 1 `render(ctx)` → provider 메시지 변환. Anthropic 어댑터는 Protocol 적합 슬롯만.

**참조 (필수)**:
- Phase 0 의 `best_agent_base/llm/` 1차 골격
- `prompt-engineering-techniques.md` — 정적/동적 경계 마커 메커니즘
- `에이전트-성능-결정요인-총정리.md` — 캐시 적중률과 비용·지연 관계
- CC `src/services/api.ts:splitSysPromptPrefix` 등 — 캐시 송신 패턴 (md + src 둘 다)

**시작 시퀀스** (Phase 0/1 패턴 동일):
1. 사용자에게 진행 모드 확인 — subagent-driven vs main-inline (디폴트는 main, 글로벌 룰)
2. **doc 작업 (brainstorm/design/write-plan) 은 main 에서 직접** — worktree 안 만듦
3. 코드 구현 단계 진입 시 **새 worktree 생성** — `git worktree add -b phase-2-cache-impl .worktrees/phase-2-cache-impl`
4. `js-super:brainstorming` 호출, slug=`phase-2-cache`
5. brainstorming → designing-direction → writing-plans → execute (subagent-driven 또는 inline) → finishing
6. **인터페이스 가이드 산출 의무**: `docs/interfaces/phase-2-cache.md` 작성 (산출물 룰 적용 — 사용예시 위, Public API 아래, 다른 모듈 연계 시 Phase 번호 X)

**Phase 1+ 그루밍 노트** (Phase 0 final review 도출 + Phase 1 에서 발견):
1. ~~README Status 라벨 갱신~~ ✅
2. `main.py` 의 `load_dotenv()` → `Settings()` 진입점 (Phase 11 Settings 시스템 시점)
3. `tests/conftest.py` 도입 — 특히 **`registry_isolation` autouse fixture** (Phase 1 의 snapshot/restore 패턴이 4 파일에서 중복. Phase 2 진입 전 또는 Phase 2 cleanup 시점에 DRY 추천)
4. `Settings.log_level` → `Literal[DEBUG, INFO, WARNING, ERROR, CRITICAL]` (Phase 11)
5. `Settings.agent_state_dir` → `Path` 정규화 (Phase 9)
6. `extra="ignore"` → `extra="forbid"` 검토 (Phase 11)
7. **노트북 setup 셀의 sys.path patch** 가 임시 — `uv add --dev jupyter ipykernel` 으로 정식 커널 등록 권장 (deps 추가는 사용자 승인 필요)
8. **Phase 0 인터페이스 가이드 backfill** — `docs/interfaces/phase-0-skeleton.md` 작성 (Settings + 9 서브패키지 + Docker setup). 시간 날 때.

---

## 🛠 환경 / 명령 빠른 참조

```bash
# 작업 디렉토리
cd /Users/goldenplanet/jinsup_space/best_agent_base

# 환경 검증
uv sync                         # deps 설치
uv run pytest -v                # 70 tests
uv run ruff check .             # All checks passed!
docker compose up -d            # postgres(5435) + redis(6379)

# Phase 1 데모 노트북
# (a) VS Code Jupyter ext 로 notebooks/phase-1-prompts-demo.ipynb 열기 (커널 .venv 선택)
# (b) 또는: uv add --dev jupyter ipykernel && uv run jupyter notebook notebooks/

# js-super 워크플로우 — doc 단계는 main, 코드 단계만 worktree
/brainstorm                     # PRD (main 에서)
/design                         # 기술 설계 (main 에서)
/write-plan                     # 구현 계획 (main 에서)
/worktree phase-N-<slug>-impl   # 코드 구현 직전 worktree 생성
/execute-plan                   # 실행 (또는 subagent-driven-development)

# 변경이력
uv run python -m scripts.change_id docs/features/<date>-<slug>
```

---

## 🔑 Quick Facts

- **Python**: 3.12+ 강제 (`.python-version`, `pyproject.toml requires-python`)
- **Default Gemini model**: `GeminiModel.FLASH` (`gemini-3-flash`) via `DEFAULT_CHAT` 프로파일
- **Postgres host port**: **5435** (사용자 환경에 5432 다른 프로젝트 점유)
- **Redis port**: 6379 (Optional, EphemeralCache backend swap)
- **Workflow plugin**: `js-super` 만 사용 (superpowers 등 안 씀)
- **사용자 이메일**: axtech@goldenplanet.co.kr
- **GitHub repo**: `LonerStayle/best_agent_base` (origin 설정됨, push 안 함)
- **테스트 카운트**: Phase 0 = 29, Phase 1 = +41, **현재 70 tests GREEN**

---

## 📋 다음 세션 시작 체크리스트

새 세션 시작 시:

1. [ ] 이 `HANDOFF.md` 한 번 통독
2. [ ] `git status && git log --oneline -10` 으로 현재 상태 확인
3. [ ] `uv run pytest && uv run ruff check .` 가 GREEN (70 tests) 인지 확인
4. [ ] 사용자가 "Phase 2 가자" 또는 다른 요청 — 그에 맞춰 진입
5. [ ] Phase 진입이면: 위 "시작 시퀀스" 그대로 따라가기 (doc 단계는 main, 코드 단계만 worktree)
6. [ ] 새 worktree 만들 때 `.worktrees/병렬구현-테스트` 는 절대 건드리지 말 것 (사용자 연구용)
7. [ ] Phase 종료 시 `docs/interfaces/phase-<N>-<slug>.md` 산출 의무 (산출물 룰 — 외부 공개 룰 + 사용예시 최상단 + Public API 최하단)
