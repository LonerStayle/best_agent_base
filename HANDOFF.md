# 인수인계 문서 — best_agent_base

> **다음 세션이 이 한 파일만 읽어도 즉시 이어갈 수 있게 작성.**
> 마지막 갱신: 2026-05-17 (Phase 3.5 mini-phase ✅ 완료 + 모델별 프롬프트 변형 슬롯 + 220 tests)

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

### Phase 0 — 프로젝트 골격 ✅ 완료 (tag `phase-0-skeleton-done`)

- 9 서브패키지 + `__init__.py` docstring-only (D-13)
- `Settings(BaseSettings)` 6 필드, lazy 인스턴스화 (D-12)
- Docker compose (postgres 5435 + redis 6379)
- LLM 카탈로그: `GeminiModel(StrEnum)` + `ModelProfile(frozen)` + 프리셋
- 29 tests GREEN

### Phase 1 — 시스템 프롬프트 7섹션 골격 ✅ 완료 (main `1a0231e` 머지)

- `best_agent_base/prompts/` 4 src — `PromptSection(Protocol)` + 7 베이스 + `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` + `SectionRegistry` + `render(ctx)` + `get_static_hash(ctx)`
- 41 신규 tests (29 → 70 GREEN), CH-001..004
- `docs/interfaces/phase-1-prompts.md` (산출물 룰 첫 적용)
- `notebooks/phase-1-prompts-demo.ipynb` (16 cells)

### Phase 2 — LLM 클라이언트 통합 (캐싱 흡수) ✅ 완료 (main `f1a1d31` — `21b27f5` 머지 + `5d88cf6` rename + `f1a1d31` wrap-up)

**산출물** (16 commits 전체, CH-20260503-001 ~ CH-20260503-017):

- `best_agent_base/llm/` — 5 신규 src + 1 재작성:
  - `client.py` — `LLMClient` Protocol (runtime_checkable, B-thin) + `LLMResponse`/`TokenUsage` (frozen)
  - `cache_policy.py` — `CachePolicy` (enabled / ttl_seconds / force_invalidate, frozen)
  - `cache_metrics.py` — `CacheEvent(StrEnum)` + `CacheObserver` + `CacheMetrics` (observer registry + counter)
  - `messages.py` — `split_at_boundary(ctx)` provider-agnostic boundary split (post-merge rename `5d88cf6` — 본래 `build_gemini_messages` 였으나 Final reviewer + Task 6.5 quality reviewer 권장으로 generic 이름화)
  - `gemini.py` — **재작성** (LangChain 제거, `google-genai` 직접 + `CachedContent` + `asyncio.Lock` per static_hash + D6 fallback)
  - `anthropic.py` — `AnthropicClient` + `cache_control: ephemeral` marker on system message
- `pyproject.toml` deps 교체 — `langchain*` 제거, `google-genai>=1.0` + `anthropic>=0.40` 추가
- `main.py` — `langgraph` → `GeminiClient` 마이그레이션 (R-3 처리)
- 7 신규 tests + 2 확장 + `tests/conftest.py` (autouse `restore_registry` — 그루밍 노트 #3 처리) = **111 tests GREEN, ruff clean**
- `docs/features/2026-05-03-phase-2-llm-client/` — PRD + tech-design + impl-plan
- **`docs/interfaces/phase-2-llm-client.md`** — 공식 인터페이스 가이드 (8섹션, Gemini ↔ Anthropic 비교 표 포함)
- **`notebooks/phase-2-llm-client-demo.ipynb`** — 데모 노트북 (산출물 룰 4부 골격, 2부에 Gemini + Anthropic 호출 예시 + provider 차이 비교 표 포함)

**핵심 검증 — provider 추상화 흡수**:
> 두 어댑터 (Gemini `CachedContent` 객체 vs Anthropic `cache_control` ephemeral marker) — 완전히 다른 캐싱 메커니즘이 동일 `LLMClient` Protocol + `CachePolicy` + `CacheMetrics` 흐름으로 흡수. 도메인 호출자는 `await client.generate(ctx, cache_policy=policy)` 한 줄로 provider 차이 모름.

### Phase 3 — 어태치먼트 시스템 (사용자 입력 + ReAct 라운드 양 지점) ✅ 완료 (main `ff4b214` — `4ed6ddf` 머지 + `749dfdf` ruff fix + `ff4b214` PRD/tech-design restore)

**산출물** (19 commits 전체, CH-20260508-001 / CH-20260510-001 / CH-20260511-001 / CH-20260511-002):

- `best_agent_base/messages.py` — `Message` + `ContentBlock` discriminated union (Anthropic content block 거울, Pydantic frozen + `Annotated[Union, Field(discriminator="type")]`)
- `best_agent_base/attachments/` — 8 신규 src + 2 builtins:
  - `protocol.py` — `Attachment(Protocol, runtime_checkable)` + `AttachmentGroup(StrEnum)` 3 값 (USER_INPUT / ALL_THREAD / MAIN_THREAD)
  - `registry.py` — `AttachmentRegistry` 모듈-레벨 싱글톤 (Phase 1 SectionRegistry 패턴 거울, register/override/get/all_in_group)
  - `collect.py` — `collect_attachments(ctx, *, user_input)` 3그룹 병렬 + null 필터 + `<system-reminder>` 자동 wrap + `is_subagent` 분기 (D9 spec deviation: `wait_for(gather)` → `wait(ALL_COMPLETED)` + cancel pending — `test_timeout_drops_slow_keeps_fast` 가 fast 결과 보존 요구)
  - `counter.py` — `count_turns_since(messages, predicate)` thinking-only 제외 (R-8)
  - `smoosh.py` — `smoosh_into_last_tool_result(messages, reminder_text)` provider strict alternation 대응, tool_use_id 보존 (R-5)
  - `gates.py` — `register_tool_pool_gate(name, predicate)` + OR 평가 (D7), `_gates: dict[str, list[ToolPoolGate]]` 모듈-레벨, NFR-1 도구 이름 박지 않음
  - `integrate.py` — `call_with_attachments(client, ctx, *, user_input, cache_policy)` helper β (D3 — Phase 2 `LLMClient.generate(ctx, *, cache_policy)` 시그니처 무변경 보존)
  - `builtins/date_change.py` — OS 시계 자정 감지, `last_emit_date` 슬롯 활용 (ALL_THREAD)
  - `builtins/todo_reminder.py` — 10 round 게이트 + counter 통합 (CC `attachments.ts:254~257` 거울), `len(ctx.todos)` 만 본문에 (D6, ALL_THREAD)
- `best_agent_base/prompts/render.py` — `RenderContext` 슬롯 5개 추가 (`messages: tuple = ()`, `todos: tuple = ()`, `tool_pool: frozenset[str] = frozenset()`, `last_emit_date: date | None = None`, `is_subagent: bool = False`) — 모두 디폴트 값 (R-6 backward compat)
- `main.py` — `call_with_attachments` helper + 베이스 디폴트 + GeminiClient 데모 마이그레이션
- 14 신규/확장 tests + `tests/conftest.py` (`restore_attachment_registry` autouse fixture 추가) = **187 tests GREEN, ruff clean** (Phase 1 70 + Phase 2 41 = 111 회귀 0건 + Phase 3 +76 = 187)
- `docs/features/2026-05-04-phase-3-attachments/` — PRD + tech-design + impl-plan
- **`docs/interfaces/phase-3-attachments.md`** — 공식 인터페이스 가이드 (8섹션, 사용 예시 7개, 위험 8개, Public API)
- **`notebooks/phase-3-attachments-demo.ipynb`** — 데모 노트북 (4부 + 실습 4개)

**핵심 검증 — 두 invariant**:
> 1. **NFR-2 정적 캐시 안전**: 어태치먼트 등록·발화 전후 `get_static_hash(ctx)` 동일 → Phase 1 BOUNDARY 위 정적 7섹션 무변경 → Phase 2 GeminiClient/AnthropicClient KV 캐시 자동 유지. helper β 가 코드 레벨로 강제 (어태치먼트는 `ctx.messages` 에만 적재).
> 2. **R-6 backward compat**: `RenderContext()` 무인자 호출 가능 → Phase 1/2 코드 0줄 수정으로 Phase 3 슬롯 자동 흡수. `RenderContext()` 호출 사이트 11개 모두 회귀 0건.

### Phase 3 중 추가된 결정·룰

- **베이스 디폴트 어태치먼트 2종 흡수**: 본래 메커니즘 골격만 (A 안) 였던 것을 사용자 결정으로 `date_change` + `todo_reminder` 본 Phase 범위에 포함 (B 안). 이유 = 메커니즘이 실제로 작동함을 산출물 노트북에서 즉시 시연 가능. 도메인 무관 어태치먼트만 박힘 (NFR-1 도메인 중립성 보존).
- **D3 β helper 패턴**: Phase 2 `LLMClient` Protocol 시그니처 변경 (α) / `ctx.user_input` 슬롯 (γ) 둘 다 비추 → 호출자가 명시적으로 `call_with_attachments(client, ctx, user_input)` helper 거침. 이유 = Phase 2 Public API 무변경 + 호출 흐름 명시적 + ReAct 루프 (Phase 5+) 가 자연스럽게 흡수.
- **D9 spec deviation accepted**: 구현계획서의 `asyncio.wait_for(gather, timeout=1.0)` → `asyncio.wait(ALL_COMPLETED) + cancel pending`. 이유 = spec 의 timeout test (`test_timeout_drops_slow_keeps_fast`) 가 fast 결과 보존 요구 → `wait_for(gather)` 는 timeout 시 모든 task 취소로 부분 결과 손실. spec reviewer accept (메인 docstring sync 처리).
- **Wave-parallel subagent-driven**: js-super-subagent-driven-development v2.0.1 — DAG 추론으로 16 task 를 5 wave 로 분할 (Wave1: 2 / Wave2: 4 / Wave3: 2 / Wave4: 3 / Wave5: 4) + 메인 inline T16 검증. Stage 1 implementer haiku byte-copy + Stage 3 spec reviewer sonnet. 메인이 wave 끝마다 plan order 직렬 commit. helper script (preflight / dag_builder / changelog_buffer) 미설치라 manifest buffer 스킵 + git diff 직접 governance.

### Phase 3.5 — 모델별 프롬프트 변형 슬롯 (mini-phase) ✅ 완료 (main `dc44faa`)

**배경**: Phase 1~3 자기검토 격차 발견 — render(ctx) 가 단일 prompt 를 두 어댑터에 동일 전달, model 별 변형 부재. CC `getAntModelOverrideSection` 슬롯 미구현. Phase 4 도구 description 도 같은 메커니즘 필요 → ROI 최대로 mini-phase 도입.

**산출물** (CH-20260517-001/002/003/004):

- `best_agent_base/prompts/model_filter.py` (신규) — `filter_model_blocks(text, model)` 헬퍼 (정규식 non-greedy + DOTALL + fnmatch glob + 중첩 거부)
- `best_agent_base/prompts/render.py` (변경) — `RenderContext.model: str | None = None` 슬롯 + `_render_static` / `_render_dynamic` 양쪽 `filter_model_blocks` 적용
- `best_agent_base/llm/{gemini,anthropic}.py` (변경) — `generate()` 시작 `ctx.model is None` 이면 자기 model 자동 주입 (`ctx.model_copy(update={"model": self_model})`, frozen ctx)
- 4 신규/확장 tests: `test_prompts_model_filter` (9) + `test_prompts_model_aware_render` (6) + `test_llm_adapter_model_injection` (4) + `test_attachments_ctx_slots` (+2) + `test_no_domain_vocab` (+12) = **+33 tests → 220 GREEN**
- `docs/interfaces/phase-3-5-model-prompts.md` (8섹션 인터페이스 가이드, 사용 예시 7개, 위험 5개, Public API)
- `notebooks/phase-3-5-model-prompts-demo.ipynb` (4부 + 실습 4개)

**핵심 검증 (3 invariant)**:

1. **R-3 backward compat** — `RenderContext.model` 디폴트 None → Phase 1~3 회귀 187 GREEN (RenderContext() 무인자 호출 11+ 사이트 무수정)
2. **NFR-3 정적 캐시 안전** — 같은 모델 호출 시 동일 hash, 다른 모델 호출 시 다른 hash → Phase 2 KV 캐시 모델별 격리
3. **NFR-1 도메인 중립성** — 베이스 `prompts/` 안에 도메인 모델 이름 (`claude-*`, `gemini-*`) grep 0건. 단 어댑터 (`llm/`) 자기 model 이름 자동 주입은 예외 OK

### Phase 3.5 중 결정·룰

- **A + D 조합 채택** — (A) RenderContext.model 슬롯 + (D) `@[MODEL: <pattern>]` 마커 런타임 필터. CC 원본 패턴에 가장 가까운 조합. 사용자 명시.
- **D2: model=None → 모든 마커 strip (조용한 정규화)** — 도메인이 model 안 박았는데 마커 박혀있으면 마커 자동 무시. Phase 1~3 backward compat 최강. ValueError 던지는 옵션 거부 (도메인 마찰).
- **D3: 어댑터 자동 주입 via `model_copy`** — frozen ctx 새 인스턴스. Phase 2 LLMClient.generate Protocol 시그니처 무변경 (B-thin 보존).
- **D4: hash 시점 = filter 후** — 같은 모델 hash 동일 (캐시 적중), 다른 모델 다른 hash (캐시 격리). raw hash 는 모델 변경 시 캐시 키 충돌.
- **D5: 중첩 마커 = ValueError** — 단일 레벨만 허용. 중첩은 구조적 모호 (외부 우선? 내부 우선?).
- **사용자 자동 진행 모드** — "yes 뒤에는 다 자동" 명시 → designing-direction / writing-plans / executing-plans 의 사용자 게이트 모두 스킵, 추천 옵션 자동 선택. main-inline 실행 (worktree 미사용, 작은 mini-phase).
- **R-1 정규식 함정 catch** — 첫 구현 시 `\s*(.*?)\s*` 가 multiline 의 leading `\n` 삼킴 → `(.*?)` 로 fix (단위 테스트가 catch).
- **`protected_namespaces=()` 추가** — Pydantic v2 가 `model_` 접두사 충돌 경고 → ConfigDict 옵션으로 회피.

### Phase 2 중 추가된 결정·룰

- **Anthropic 어댑터 흡수**: 본래 OOS-1 ("Anthropic 어댑터 본 구현") 였던 항목을 사용자 결정으로 본 Phase 2 범위에 포함 (CH-010/011/012 cascade). 이유 = provider 추상화의 진정한 검증은 2개 어댑터를 같이 만들어야 가능.
- **산출물 룰 갱신**: 인터페이스 가이드 + 데모 노트북 **두 산출물** 모두 의무 (이전엔 인터페이스 가이드만). 노트북은 4부 골격 (베이스 → register/override → escape hatch + 위험 가드 + cleanup + 다른 모듈 연계 + 실습 4개) + Phase 번호 X + 사용자 직접 수정 보존 + ipykernel 정식 등록 권장.
- **메트릭 계약 명문화**: `HASH_CHANGE` 는 같은 호출 안에서 후속 `MISS` 와 union 으로 발생하는 *causal annotation* — 합산 시 cache 압력 overcount.
- **D6 SDK 예외 정책**: SDK 예외 그대로 전파, 단 Gemini `caches.create` 실패는 None 반환 → 캐시 우회 fallback (캐시 가용성과 호출 가용성 분리).

### git 상태

- 브랜치: `main` (HEAD `dc44faa` — Phase 3.5 mini-phase 완료, main-inline 직접 commit)
- `phase-3-attachments-impl` 브랜치/워크트리 — 머지 후 정리됨 (`git worktree remove --force`)
- Phase 3.5 는 worktree 미사용 (작은 mini-phase + 사용자 자동 진행 모드 — main 직접 6 task commit)
- **`.env` / `.env.example` 환경 변수**: Phase 2 의 `GOOGLE_API_KEY` + `ANTHROPIC_API_KEY` 그대로
- **`.worktrees/병렬구현-테스트` 절대 건드리지 말 것** (사용자 연구용)
- origin (GitHub `LonerStayle/best_agent_base`) — push 안 함
- tag `phase-0-skeleton-done` → `68c91a9` (Phase 1·2·3 종료 시 새 tag 미생성)

---

## 🆕 산출물 룰 — 두 산출물 의무 (인터페이스 가이드 + 데모 노트북)

> 자세한 내용: [`TODO.md` §📖 산출물 룰](./TODO.md#-산출물-룰--각-phase-끝마다-인터페이스-개발문서--데모-노트북-두-산출물)

**산출물 1: 인터페이스 가이드** (`docs/interfaces/phase-<N>-<slug>.md`)
- 8섹션: 모듈책임 / 사용예시 (위) / 핵심개념 (도표) / 확장포인트 / 위험 / 다른 모듈 연계 (Phase 번호 X, 기능명만) / 데모 노트북 / Public API (아래)
- 변경이력 섹션 두지 않음

**산출물 2: 데모 노트북** (`notebooks/phase-<N>-<slug>-demo.ipynb`)
- 4부 골격: Setup / 1부 베이스 → 2부 register/override → 3부 escape hatch + 위험 가드 → cleanup → 다른 모듈 연계 → 실습 4개
- 사용자 직접 수정 보존 (Write 로 덮어쓰기 금지, NotebookEdit 사용)
- ipykernel 정식 등록 권장 (`uv add --dev jupyter ipykernel`)

**검증**: 다음 Phase 진입 시 직전 Phase 의 두 산출물 모두 존재 확인. 없으면 진입 전 작성.

---

## ✅ What Worked (Phase 2 에서 추가 확인)

- **`js-super` 풀 사이클** — Phase 0/1/2 세 번 모두 깨끗 완성
- **Subagent-driven-development** — Phase 2 = 9 implementer + 9×2 reviewer (spec+quality) + 1 final = 28회 dispatch + Task 6.5 추가 (3회 더). Task 4·6·6.5 만 reviewer Important 발견 → 메인이 직접 fix → 나머지 nit-only PASS.
- **TDD RED → GREEN** — 9 task + 1 추가 task 모두 test-first.
- **Worktree-per-Phase** — `.worktrees/<phase-name>-impl` 깨끗 머지 후 정리.
- **change-history cross-link** — Phase 2: 17 entries 가 PRD/tech-design/plan/code 모두 cross-link.
- **cascading update 패턴** — 사용자가 Anthropic 추가 요청 → PRD/tech-design/plan/TODO/HANDOFF cascade. CH-010/011/012 로 추적 가능.
- **context7 MCP 활용** — Anthropic SDK + google-genai SDK 시그니처 코드 작성 전 검증. Task 6/6.5 implementer 모두 5/5 시그니처 일치 확인.

---

## ❌ What Didn't Work / 주의

- **Worktree branch ↔ main 동시 변경 시 sync 복잡도** — Phase 2 cascading update 시 main 의 PRD/tech-design 만 sync, TODO.md/HANDOFF.md 는 누락 → 머지 직전 sync commit (`8efdb02`) 필요. **다음 Phase**: 코드 단계 진입 전 main 의 doc 들 모두 worktree 로 cp 한 번에.
- **`MagicMock(name=...)` 함정** — Task 6 implementer 가 plan 의 `MagicMock(name="cachedContents/abc")` 가 mock repr 인자로 잡혀 attribute 안 됨을 발견. `m = MagicMock(); m.name = "..."` 로 fix. 다음 SDK mock 작성 시 동일 패턴 주의.
- **노트북 ruff 잔여** — `notebooks/phase-1-prompts-demo.ipynb` 의 9 errors (F541/I001/E501) 가 Phase 2 commit 들에 carry-over. Phase 작업 외 별도 commit 으로 그루밍 권장.
- **사용자 글로벌 CLAUDE.md 룰**: "탐색/플래닝 → 서브에이전트, 실행 → 메인" — Phase 0/1/2 모두 사용자가 명시적으로 subagent-driven 선택. 다음 Phase 부터 디폴트 = 메인 실행, subagent-driven 은 사용자 명시 시에만.
- **CC `src/contextCollapse/` 와 `snipCompact.js`** — TS 본체 비공개 (.js only). Phase 9 진입 시 직접 알고리즘 설계 필요.

---

## 🔧 핵심 설계 원칙 (8가지, 모든 Phase 관통)

> [`TODO.md` §🧭 설계 원칙](./TODO.md#-설계-원칙-모든-phase에-관통) 참조

1. 정적/동적 분리 (Caching Boundary) — Phase 1 의 BOUNDARY 마커 + Phase 2 의 GeminiClient/AnthropicClient 캐싱 통합으로 본격 실현
2. "안 만들기" 원칙 — Phase 2 KV 캐싱 단독 Phase 폐기 + 호출 레이어 흡수 결정의 근거
3. 조용한 정규화
4. 3그룹/3레이어 병렬 분담
5. 관찰→교정→재관찰 (`@[MODEL: ...]` 마커)
6. 에러는 모델 피드백 (envelope) — Phase 2 D6 = SDK 예외 그대로 전파, envelope 는 도구 베이스 Phase
7. 격리된 컨텍스트 (Subagent Isolation)
8. 교체·확장 가능성 — Phase 1 `SectionRegistry.register()` + Phase 2 `LLMClient` Protocol runtime_checkable 으로 두 번 적용

---

## 🛤️ Next Steps — Phase 3.5 mini-phase **먼저** (Phase 4 진입 전 필수)

> **Phase 1~3 자기검토에서 발견**: 현재 `render(ctx)` 가 단일 prompt 를 두 어댑터에 동일 전달 → 모델별 프롬프트 변형 불가. CC `@[MODEL: ...]` 마커 시스템 (원칙 #5) 슬롯 미구현. Phase 4 도구 베이스도 모델별 description 변형 필요 → Phase 3.5 mini-phase 로 같이 박는 게 ROI 최대.

### Phase 3.5 — 모델별 프롬프트 변형 슬롯 (mini-phase)

> [`TODO.md` §🎚️ Phase 3.5](./TODO.md#%EF%B8%8F-phase-35--모델별-프롬프트-변형-슬롯-mini-phase-phase-4-진입-전-필수) 참조

**핵심**: `RenderContext.model` 슬롯 + `@[MODEL: <pattern>] ... @[/MODEL]` 마커 + `filter_model_blocks` 헬퍼 + 어댑터 자동 model 주입 + Phase 1~3 backward compat (마커 없는 코드는 모든 모델에서 동일 출력).

**참조 (필수)**: `prompt-engineering-techniques.md`, `cc-analysis/17-getAntModelOverrideSection-analysis.md` (CC `getAntModelOverrideSection` 분석 — 모델별 교정 ground truth), 원칙 #5 관찰→교정→재관찰

**시작 시퀀스**:
1. 사용자에게 진행 모드 확인 — 작은 mini-phase 라 main-inline 권장 (subagent-driven 오버헤드 ↑)
2. doc 단계 main 에서 — `js-super:brainstorming` slug=`phase-3-5-model-prompts`
3. brainstorming → designing-direction → writing-plans → execute (inline) → finishing
4. **두 산출물 의무**: `docs/interfaces/phase-3-5-model-prompts.md` + `notebooks/phase-3-5-model-prompts-demo.ipynb`

### Phase 4 — 도구 베이스 + 도구 설명 패턴 (L1/L2/L3) (Phase 3.5 후 진입)

> [`TODO.md` §🛠️ Phase 4](./TODO.md#%EF%B8%8F-phase-4--도구-베이스--도구-설명-패턴l1l2l3) 참조

**핵심**: `Tool` 추상 (`name` / `description` / `input_schema(pydantic)` / `validate_input()` / `call()`) + 3레이어 규칙 분리 (L1 시스템 프롬프트 / L2 description 6패턴 / L3 코드 검증) + 가벼운 빌트인 도구만 (Echo / Calc / ToolSearch / 카피 도구 7~8개) + 에러 envelope (`{ok, error, hint, retryable}` — 원칙 #6).

**참조 (필수)**:
- `에이전트-개발-인사이트_cc분석.md` — 도구 description 6패턴 (P1 금지 / P2 실패 / P3 대안 / P4 if/when / P5 전제 / P6 예시)
- `에이전트-성능-결정요인-총정리.md` — 3레이어 도구 설계 + L2 description 의 무게중심
- `도구-실행-10단계-파이프라인.md` — `checkPermissionsAndCallTool` 10단계 (Phase 5 ReAct 와도 연결)

**시작 시퀀스** (Phase 0/1/2/3 패턴 동일):
1. 사용자에게 진행 모드 확인 — subagent-driven vs main-inline (디폴트는 main-inline, 글로벌 룰)
2. **doc 작업 (brainstorm/design/write-plan) 은 main 에서 직접** — worktree 안 만듦
3. 코드 구현 단계 진입 시 **새 worktree 생성** — `git worktree add -b phase-4-tools-impl .worktrees/phase-4-tools-impl`
4. **코드 단계 진입 전 main 의 doc 들 worktree 로 cp** (Phase 2/3 lesson learned — `cp -r docs/features/<date>-<slug> .worktrees/<branch>/docs/features/`)
5. `js-super:brainstorming` 호출, slug=`phase-4-tools`
6. brainstorming → designing-direction → writing-plans → execute (subagent-driven 또는 inline) → finishing
7. **두 산출물 의무**: `docs/interfaces/phase-4-tools.md` + `notebooks/phase-4-tools-demo.ipynb`

**Phase 3+ 그루밍 노트** (Phase 1/2 carry + Phase 3 발견):
1. ~~`tests/conftest.py` 도입 (autouse `restore_registry`)~~ ✅ Phase 2 Task 9 처리
2. `main.py` 의 `load_dotenv()` → `Settings()` 진입점 (Phase 11)
3. `Settings.log_level` → `Literal[DEBUG, INFO, WARNING, ERROR, CRITICAL]` (Phase 11)
4. `Settings.agent_state_dir` → `Path` 정규화 (Phase 9)
5. `extra="ignore"` → `extra="forbid"` 검토 (Phase 11)
6. **노트북 setup 셀 sys.path patch** 임시 — `uv add --dev jupyter ipykernel` 정식 등록 (deps 추가 사용자 승인 필요)
7. **Phase 0 인터페이스 가이드 + 데모 노트북 backfill** — `docs/interfaces/phase-0-skeleton.md` + `notebooks/phase-0-skeleton-demo.ipynb`
8. ~~**`build_gemini_messages` rename**~~ ✅ Phase 2 wrap-up `5d88cf6` 에서 처리
9. **`count_tokens` Phase 9 마이그레이션** — 두 어댑터 모두 placeholder. 정식 SDK API 로 교체
10. **Anthropic 1h extended cache** — D7 deferred. ephemeral 1종 단순화. ttl_seconds >= 3600 시 1h 매핑 검토
11. **노트북 ruff 잔여** — `notebooks/phase-1-prompts-demo.ipynb` 9 errors carry-over
12. **`RenderContext.todos` 정식 타입** — 현재 `tuple = ()` (D6, Phase 5+ TodoWrite 도구가 형식 정의 시 좁히기)
13. **`RenderContext.tool_pool`** — 현재 frozenset[str] 단순. Phase 4/5 도구 베이스에서 ToolName / ToolMetadata 객체로 강화 검토
14. **subagent helper script 미설치** — `scripts/{preflight,dag_builder,changelog_buffer}` 가 js-super-subagent-driven-development v2.0.1 가 요구. 현재 manual fallback. Phase 4+ 진입 전 설치 권장 (또는 main-inline 디폴트 사용)
15. **Phase 3 worktree merge 시 PRD/tech-design 누락** 사고 — worktree 안에서 untracked 였어 머지 누락 → main 에서 cp + 별도 commit 으로 복원. **다음 Phase**: 코드 진입 전 main 에서 docs 먼저 commit 후 worktree cp (lesson)
16. **`call_with_attachments` helper β** — Phase 5 ReAct 루프가 흡수하면 `attachments/integrate.py` 단독 helper 는 deprecate 검토 (단 노트북 데모용으로 유지 가능)

---

## 🛠 환경 / 명령 빠른 참조

```bash
# 작업 디렉토리
cd /Users/goldenplanet/jinsup_space/best_agent_base

# 환경 검증
uv sync                                         # deps 설치
uv run pytest -v                                # 187 tests
uv run ruff check best_agent_base/ tests/ main.py  # All checks passed!
docker compose up -d                            # postgres(5435) + redis(6379)

# Phase 2/3 데모
uv run python main.py                           # call_with_attachments + GeminiClient (GOOGLE_API_KEY 필요)

# 데모 노트북 (Phase 1 + Phase 2 + Phase 3)
# (a) VS Code Jupyter ext 로 notebooks/phase-N-*.ipynb 열기 (커널 .venv 선택)
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

- **Python**: 3.12+ 강제
- **Default Gemini model**: `GeminiModel.FLASH` via `DEFAULT_CHAT` 프로파일
- **Default Anthropic model**: `claude-sonnet-4-5-20250929` via `AnthropicClient()` 디폴트
- **Postgres host port**: **5435**
- **Redis port**: 6379 (Optional)
- **환경 변수**: `GOOGLE_API_KEY` + `ANTHROPIC_API_KEY` + `DATABASE_URL` + `REDIS_URL` (Optional) + `BLOB_STORE_URL` (Optional). `.env.example` 참조.
- **Workflow plugin**: `js-super` 만 사용
- **사용자 이메일**: axtech@goldenplanet.co.kr
- **GitHub repo**: `LonerStayle/best_agent_base` (origin 설정됨, push 안 함)
- **테스트 카운트**: Phase 0 = 29 / Phase 1 = +41 (70) / Phase 2 = +41 (111) / Phase 3 = +76 (187) / Phase 3.5 = +33 (220). **현재 220 tests GREEN**

---

## 📋 다음 세션 시작 체크리스트

1. [ ] 이 `HANDOFF.md` 한 번 통독
2. [ ] `git status && git log --oneline -10` 으로 현재 상태 확인 (예상: HEAD `dc44faa` Phase 3.5 wrap-up)
3. [ ] `uv run pytest && uv run ruff check best_agent_base/ tests/ main.py` 가 GREEN (220 tests) 인지 확인
4. [ ] 사용자가 "Phase 4 가자" 또는 다른 요청 — 그에 맞춰 진입
5. [ ] Phase 진입이면: 위 "시작 시퀀스" 그대로 따라가기 (doc 단계는 main, 코드 단계만 worktree)
6. [ ] 새 worktree 만들 때 `.worktrees/병렬구현-테스트` 는 절대 건드리지 말 것 (사용자 연구용)
7. [ ] Phase 종료 시 **두 산출물** 의무: `docs/interfaces/phase-<N>-<slug>.md` + `notebooks/phase-<N>-<slug>-demo.ipynb` (산출물 룰 — 외부 공개 + 사용예시 위 + Public API 아래)
8. [ ] **코드 진입 전 main 에서 docs/features/<slug>/ commit 후 worktree cp** (Phase 3 lesson — worktree untracked PRD/tech-design 머지 시 누락)
