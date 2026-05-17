# 요구사항: Phase 3.5 — 모델별 프롬프트 변형 슬롯 (mini-phase)

> **For agentic workers:** This document is the PRD (planning-level only). NEXT STEP: invoke `designing-direction` skill (or run `/design`) to produce `phase-3-5-model-prompts-tech-design.md` from this document. Do NOT add tech decisions or implementation details here — those belong in the next two artifacts.

## 1. 배경/목적

Phase 1~3 자기검토에서 발견된 격차 — 현재 `render(ctx)` 가 단일 prompt string 을 두 어댑터 (Gemini / Anthropic) 에 **동일하게** 전달. provider/model 별 프롬프트 변형 인터페이스 부재.

근거:

1. **CC 원칙 #5 관찰→교정→재관찰** — 모델 실패 패턴은 `@[MODEL: <model> <yyyy-mm>]` 마커로 description·프롬프트에 기록·축적. 현재 베이스에 슬롯 자리는 잡혀있으나 본격 구현 미진.
2. **CC `getAntModelOverrideSection`** (`/Users/goldenplanet/jinsup_space/CC/cc-analysis/17-getAntModelOverrideSection-analysis.md`) — Claude Code 가 모델 버전별 시스템 프롬프트 교정을 실제 운영하는 ground truth.
3. **Phase 4 도구 베이스 진입 전 필수** — 도구 description 도 모델별 변형이 거의 확실히 필요 (CC 패턴). Phase 3.5 에서 마커 시스템을 박아두면 Phase 4 가 같은 메커니즘 재사용 → ROI 최대.
4. **CLAUDE.md §2 룰 #3 — Gemini wire 한계 존중하면서 통합 추상으로 흡수** — Gemini 와 Anthropic 의 미묘한 프롬프트 선호 차이를 베이스가 흡수 (예: Anthropic 의 XML 태그 친화 vs Gemini 의 markdown 친화) — 도메인이 매번 ctx 분기 안 짜도 되게.

목적: **A + D 조합 채택** — (A) `RenderContext.model` 슬롯 + (D) `@[MODEL: <pattern>]` 마커 런타임 필터. 가장 작은 베이스 변경 + CC 원본 패턴에 가장 가까움 + Phase 1~3 backward compat 0건 회귀.

## 2. 사용자 스토리 / 시나리오

해당 없음 — 내부 인프라 (도메인 에이전트 개발자가 사용하는 베이스 슬롯). 외부 사용자 노출 X.

대신 **도메인 개발자 시나리오 1개** (참고):

> FastAPI 의료 에이전트 개발자 K 는 Claude 모델에는 `<context>` XML 태그로 환자 컨텍스트 감싸야 응답 정확도가 올라가고, Gemini 모델은 markdown `## 컨텍스트` 헤딩이 더 잘 인식된다는 걸 관찰. 두 모델 모두 지원해야 하는 멀티-provider 도메인이라 매번 ctx 분기 코드를 도메인에 짜는 게 번거로움.
> Phase 3.5 베이스 슬롯이 있으면 K 는 PromptSection 안에 `@[MODEL: claude-*]<context>...</context>@[/MODEL] @[MODEL: gemini-*]## 컨텍스트 ... @[/MODEL]` 한 번 박고 끝. `LLMClient` 가 자기 model 이름을 ctx 에 자동 주입 → render 시 filter_model_blocks 가 매칭 안 되는 블록 자동 strip.

## 3. 기능 요구사항 (FR)

- **FR-1: `RenderContext.model: str | None = None` 슬롯 추가** — Phase 1 의 빈 모델 design intent 그대로 확장. 디폴트 None = 모델-무관 모드 (Phase 1~3 backward compat). 도메인이 명시적으로 박을 때는 정식 모델 이름 (예: `"claude-sonnet-4-5-20250929"`, `"gemini-2.5-flash"`).
- **FR-2: `@[MODEL: <pattern>] ... @[/MODEL]` 마커 시스템** — PromptSection 의 `render(ctx)` 결과 안에 마커 블록 박을 수 있어야 함. `<pattern>` 은 fnmatch glob (예: `claude-*`, `gemini-*`, `claude-sonnet-4-*`, `*`). 매칭 모델일 때 블록 내용 keep, 아니면 블록 전체 strip (마커 라인 포함).
- **FR-3: `filter_model_blocks(text: str, model: str | None) -> str` 헬퍼** — `best_agent_base/prompts/model_filter.py` (신규). 텍스트 안 모든 `@[MODEL:...]...@[/MODEL]` 블록 파싱 + glob 매칭 + 미매칭 블록 strip. `model=None` 시 모든 마커 블록 strip (조용한 정규화 — 도메인이 model 안 박으면 마커 그냥 무시, 디폴트 텍스트만 노출).
- **FR-4: `render(ctx)` 통합** — `_render_static(ctx)` + `_render_dynamic(ctx)` 결과 각각에 `filter_model_blocks(..., ctx.model)` 적용. 정적 7섹션 안에 모델별 변형 블록 박혀 있어도 `get_static_hash(ctx)` 는 모델 필터 **이후** 의 텍스트를 해시 → 같은 모델 호출 시 같은 hash (= 캐시 적중 유지), 다른 모델 호출 시 다른 hash (= 모델별 독립 캐시).
- **FR-5: `LLMClient` 어댑터 자동 model 주입** — `GeminiClient.generate` / `AnthropicClient.generate` 시작 시 `ctx.model is None` 이면 자기 model name (`self._profile.model.value` / `self._model`) 으로 `ctx.model_copy(update={"model": ...})` 새 ctx 만들어서 render. 도메인이 명시적으로 박았으면 (`ctx.model is not None`) 그대로 사용 (도메인 우선).
- **FR-6: 중첩 마커 거부** — `@[MODEL:...]...@[MODEL:...]...@[/MODEL]...@[/MODEL]` 같은 중첩은 `ValueError` (구조적으로 모호함). 단일 레벨만 허용.

## 4. 비기능 요구사항 (NFR)

- **NFR-1: 도메인 중립성** — 베이스 코드/docstring 안에 모델 이름 (`"claude-*"`, `"gemini-*"` 등) 박지 않음. 단 어댑터 안 자기 model 이름 자동 주입 (Gemini `_profile.model.value` / Anthropic `_model`) 은 OK (= 자기 정체성). regex grep 테스트 (Phase 1 패턴) — 신규 `model_filter.py` 까지 grep 범위 확장.
- **NFR-2: Phase 1~3 backward compat** — `RenderContext()` 무인자 호출 가능, 마커 없는 코드 = 모든 모델에서 동일 출력. 187 tests GREEN 회귀 0건.
- **NFR-3: 정적 캐시 안전 invariant** — `get_static_hash(ctx)` 는 `filter_model_blocks` 이후 텍스트를 해시. 같은 모델 호출 시 hash 동일 (캐시 적중), 다른 모델 호출 시 hash 다름 (모델별 독립 캐시). Phase 2 의 `CachedContent` / `cache_control` 메커니즘과 호환.
- **NFR-4: `__init__.py` docstring-only (D-13)** — `prompts/__init__.py` 그대로 (Phase 1 골격 유지). 신규 `model_filter.py` 는 `prompts/` 하위라 추가 변경 X.

## 5. 범위 밖 (Out of Scope)

1. **모델 이름 사전 / catalog** — 어떤 모델이 있는지 베이스가 정의 X. 도메인이 자기 ctx.model 에 채움 (Phase 0 의 `GeminiModel(StrEnum)` 은 Gemini 한정, 도메인 catalog 확장은 도메인 책임).
2. **모델별 prompt 본문 콘텐츠** — 베이스는 빈 슬롯 + 마커 메커니즘만. "Claude 한테는 XML, Gemini 한테는 markdown" 같은 콘텐츠는 도메인이 자기 PromptSection.render(ctx) 안에 마커로 박음.
3. **다른 조건부 블록 시스템** — `@[CONTEXT_SIZE: large]...@[/CONTEXT_SIZE]`, `@[USER_ROLE: admin]...@[/USER_ROLE]` 같은 다른 차원 조건부는 X. 본 Phase 는 `@[MODEL: ...]` 만.
4. **마커 자동 파싱 메트릭** — 모델별 prompt 변형 빈도 / 어느 모델용 블록이 가장 많이 발화 등의 메트릭은 X (관찰 가능성은 후속 Phase).
5. **어댑터 외 다른 진입점에서 model 자동 주입** — `render(ctx)` 단독 호출 시 ctx.model None 이면 그대로 None (= 모든 마커 블록 strip). 진입점은 LLMClient 어댑터 한 곳만.
6. **모델 버전별 timestamp 매칭** (CC 의 `@[MODEL: claude-3 2024-09]` 형식의 날짜 부분) — 본 Phase 는 모델 이름 glob 매칭만. 날짜 매칭은 OOS (도메인이 모델 이름에 버전 포함시키면 글로브로 처리 가능).
7. **PromptSection 외 다른 곳 (도구 description, 어태치먼트 build 결과) 에서 마커 사용** — Phase 4+ 에서 같은 `filter_model_blocks` 헬퍼 재사용해서 적용 (본 Phase 는 prompts/ 한정).
8. **어댑터의 자동 주입 disable 옵션** — 도메인이 ctx.model 박으면 그게 우선, 안 박으면 어댑터가 자동 주입. 명시적 "자동 주입 꺼" 옵션은 X (필요하면 도메인이 `ctx.model = "_disabled"` 같은 sentinel 박음 — OOS).

## 6. 수용 기준 (Acceptance Criteria)

- **AC-1**: `RenderContext.model` 슬롯 정의됨, 디폴트 None, frozen 모델 보존. `RenderContext()` 무인자 호출 가능 (Phase 1~3 회귀 0건). (FR-1, NFR-2)
- **AC-2**: `filter_model_blocks("text @[MODEL: claude-*]ABC@[/MODEL] tail", "claude-sonnet-4-5-20250929")` → `"text ABC tail"` (매칭 keep). (FR-2, FR-3)
- **AC-3**: `filter_model_blocks("text @[MODEL: claude-*]ABC@[/MODEL] tail", "gemini-2.5-flash")` → `"text  tail"` (미매칭 block 전체 strip 마커 라인 포함). (FR-2, FR-3)
- **AC-4**: glob 패턴 정확 — `"claude-*"` / `"gemini-*"` / `"*"` / `"claude-sonnet-4-*"` 모두 fnmatch 표준 동작. (FR-2)
- **AC-5**: `filter_model_blocks("@[MODEL: *]X@[/MODEL]", None)` → `""` (model=None 시 모든 마커 블록 strip). (FR-3)
- **AC-6**: 중첩 마커 (`@[MODEL: a]@[MODEL: b]X@[/MODEL]@[/MODEL]`) → `ValueError` raise. (FR-6)
- **AC-7**: `render(ctx)` 가 _render_static + _render_dynamic 결과 양쪽에 filter_model_blocks 적용 (단위 테스트 — 모델별로 다른 텍스트 매칭 시 다른 hash, 같은 모델 두 번 호출 시 같은 hash). (FR-4, NFR-3)
- **AC-8**: `GeminiClient.generate(ctx)` 호출 시 `ctx.model is None` 이면 어댑터가 `self._profile.model.value` 로 model 자동 주입 (mock 테스트 — `client.generate` 호출 후 split_at_boundary 가 모델 매칭된 텍스트 반환). (FR-5)
- **AC-9**: `AnthropicClient.generate(ctx)` 호출 시 동일하게 `self._model` 자동 주입. (FR-5)
- **AC-10**: `ctx.model="my-custom-model"` 명시 박혀 있으면 어댑터가 그걸 우선 사용 (자동 주입 우회). (FR-5)
- **AC-11**: `tests/test_no_domain_vocab.py` grep 범위에 `model_filter.py` 추가. 도메인 모델 이름 (`claude-*`, `gemini-*`) 베이스 코드 안 0건 — 단 어댑터 안 자기 model 자동 주입은 grep 검사 대상 외 (이미 Gemini / Anthropic 어댑터는 자기 model 이름 박혀있음, 그게 정상). (NFR-1)
- **AC-12**: 전체 테스트 GREEN — Phase 1 70 + Phase 2 41 + Phase 3 76 = 187 회귀 0건 + Phase 3.5 신규 ~25 = **~212 tests GREEN**. ruff clean. (NFR-2)

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-17 12:00] [요구사항-수정]
- **id**: CH-20260517-001
- **이유**: Phase 1~3 자기검토에서 발견된 model-aware prompt 변형 슬롯 격차 — A+D 조합 (RenderContext.model 슬롯 + @[MODEL: ...] 마커 런타임 필터) mini-phase brainstorming 결과
- **무엇이**: phase-3-5-model-prompts-requirements.md 전체 (FR-1..6, NFR-1..4, AC-1..12, OOS 8항목)
- **영향범위**: 없음 (최초 생성). Phase 4 도구 베이스 진입 전 필수 — Phase 4 가 같은 마커 메커니즘 재사용 가능
