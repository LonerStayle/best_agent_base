# 요구사항: LLM 클라이언트 통합 (캐싱 흡수)

> **For agentic workers:** This document is the PRD (planning-level only). NEXT STEP: invoke `designing-direction` skill (or run `/design`) to produce `phase-2-llm-client-tech-design.md` from this document. Do NOT add tech decisions or implementation details here — those belong in the next two artifacts.

## 1. 배경/목적

Phase 1 에서 시스템 프롬프트의 정적/동적 분리 골격(7 섹션 + `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커 + `get_static_hash(ctx)`) 을 만들었지만, 그 출력이 실제 LLM 호출까지 도달하는 종단 경로는 아직 없다. Phase 0 의 `best_agent_base/llm/` 1차 골격은 모델 카탈로그 + 프로파일 + 단순 팩토리 수준에 그쳐, 캐싱·메시지 빌더·provider 교체 슬롯이 빠져 있다.

본 Phase 2 의 목적은 다음 세 가지를 한꺼번에 박는 것이다:

- **(A) 호출 레이어 베이스화** — Phase 1 `render(ctx)` 출력이 실제 LLM 호출까지 도달하는 첫 종단 경로를 베이스에서 제공한다. 도메인 프로젝트가 모델 호출 코드를 다시 짤 필요 없게.
- **(B) 얇은 provider 추상화 (B-thin) + 2개 참조 구현** — `LLMClient` Protocol 1개 + Gemini + Anthropic 참조 구현 2개. 두 provider 의 캐싱 메커니즘 차이 (Gemini `CachedContent` vs Anthropic `cache_control` ephemeral marker) 를 통합 인터페이스 (`CachePolicy`) 로 흡수. 도메인은 provider 차이 모르고 동일 호출 경로 사용. 사내 LLM / vLLM 등은 도메인이 자기 어댑터 등록 슬롯 사용.
- **(C) KV 캐싱 통합·컨트롤** — Phase 1 boundary 마커 위(static)만 캐시 대상으로 삼아 Gemini `CachedContent` 자동 적용. 동일 `ctx` 재호출 시 캐시 재사용 + 도메인이 TTL · on/off · 강제 무효화 컨트롤 가능 + 적중률을 메트릭 슬롯으로 노출.

본래 14 Phase 로드맵에서 "Phase 2 — KV 캐싱(프롬프트 캐싱) 적용" 으로 분리돼 있던 항목은 호출 레이어가 없는 시점에 캐시 인프라만 만드는 것이 D-2("안 만들기") 위반이라는 판단에 따라 LLM 클라이언트 Phase 에 흡수됐다 (TODO.md §🧊 Phase 2 결정 박스 참조). 핵심 본질은 여전히 **"KV 캐싱이 유지되거나 컨트롤 가능한가"** 이며, 본 Phase 2 의 deliverable 평가도 이 질문으로 한다.

## 2. 사용자 스토리 / 시나리오

- **US-1 (도메인 통합 사용)** — 도메인 프로젝트가 LLM 호출 코드를 직접 짜지 않고 베이스가 노출하는 호출 함수 한 줄로 호출한다. 모델 선택 · 캐시 적용 · 메시지 빌더가 자동 처리되어, 도메인 코드에는 비즈니스 로직만 남는다.
- **US-2 (provider 교체)** — 도메인이 자기 provider (예: 사내 LLM / vLLM 호스팅 / Anthropic) 를 끼워야 할 때 `LLMClient` Protocol 만 구현·등록해서 베이스 호출 경로를 그대로 쓴다. 베이스 코드 0 줄 수정 (Open/Closed, D-8).
- **US-3 (캐시 가시성)** — 베이스를 운영하는 사람이 캐시 적중률 · 미적중 · 정적 해시 변화를 로그/메트릭으로 확인해서 비용·지연 회귀를 감지한다.

## 3. 기능 요구사항 (FR)

- **FR-1** `LLMClient` Protocol 정의 (얇게) — `async generate(messages, *, cache_policy=None) → response` + `count_tokens(...)` 슬롯. provider 등록·교체 슬롯으로 동작.
- **FR-2** Gemini 어댑터 참조 구현 — Phase 0 `get_gemini` 1차 골격 위에서 확장 또는 새 클래스로 `LLMClient` 적합 구현 제공.
- **FR-3** Phase 1 `render(ctx)` → Gemini 메시지 구조 변환 — `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 위/아래 분리 보존 (정적부 = 캐시 대상, 동적부 = 매 턴 재계산).
- **FR-4** Gemini `CachedContent` 자동 적용 — 정적 부만 캐시, cache key = `get_static_hash(ctx)`. 동일 `ctx` 재호출 시 캐시 재사용.
- **FR-5** **캐시 컨트롤 인터페이스** — 도메인이 `CachePolicy` (TTL · on/off · 강제 무효화 · provider-별 옵션) 로 캐시 동작을 명시 컨트롤할 수 있다. 베이스는 `CachePolicy` frozen 모델과 디폴트 정책을 제공한다.
- **FR-6** 캐시 메트릭 슬롯 — 적중·미적중·정적 해시 변화를 이벤트로 발생, observer (callable) 등록 인터페이스 제공. 베이스는 인터페이스만, 실제 메트릭 backend (Prometheus / OTel / 로깅 등) 는 도메인 책임.
- **FR-7** Anthropic 어댑터 참조 구현 — `LLMClient` 적합 `AnthropicClient` 클래스 (`anthropic.AsyncAnthropic` SDK 직접 사용). 정적부 = system 메시지 마지막 text block 에 `cache_control: {"type": "ephemeral"}` marker 부착. `CachePolicy.enabled=False` 면 marker 미부착 (캐시 우회). 동일 `LLMClient` Protocol + `CachePolicy` + `CacheMetrics` 흐름으로 Gemini 와 통합 — 도메인은 provider 차이 모름.

## 4. 비기능 요구사항 (NFR)

- **NFR-1 (도메인 중립성)** — 베이스 LLM 클라이언트 코드 / 디폴트 메시지 / 에러 텍스트에 도메인 어휘(코딩/의료/금융/etc.) 금지. Phase 1 의 `tests/test_no_domain_vocab.py` 검증을 `best_agent_base/llm/` 트리에 확장 적용.
- **NFR-2 (D-13 docstring-only `__init__.py`)** — `best_agent_base/llm/__init__.py` 는 docstring-only 유지. Phase 2 신규 추상 추가 시 AST 검증으로 재확인.
- **NFR-3 (캐시 키 결정성)** — 동일 `ctx` → 동일 cache key. 캐시 키 derivation 전 과정에서 시간 · 랜덤 · 환경 변수 등 외부 의존 금지.
- **NFR-4 (테스트 커버리지)** — 모든 FR 마다 단위 테스트 + 캐시 적중 통합 테스트 (SDK mock 또는 record/replay) 동반. Phase 1 패턴 (snapshot/restore fixture, AST 검증) 일관 적용.

## 5. 범위 밖 (Out of Scope)

본 Phase 의 범위를 좁혀 D-2 ("안 만들기") 와 추상화 두려움(미숙한 다중-provider 추상화) 회피.

1. ~~**Anthropic 어댑터 본 구현**~~ — **CH-20260503-010 에서 본 Phase 2 범위에 포함 결정** (FR-7). cache_control ephemeral marker 메커니즘으로 Gemini `CachedContent` 와 통합 인터페이스 (`CachePolicy`) 흡수.
2. **LangChain 유지/제거 결정** — 현재 1차 골격이 `langchain_google_genai.ChatGoogleGenerativeAI` 위에 있음. 유지 vs 직접 `google-genai` SDK 사용 결정은 tech-design 단계.
3. **`count_tokens` 본격 구현** — FR-1 에 인터페이스 슬롯만. 실제 토큰 카운팅 로직은 컨텍스트 관리 Phase 에서 본격 구현.
4. **스트리밍 응답** — 베이스 호출 시그니처에 streaming 모드 미포함. ReAct 루프 Phase 에서 본격.
5. **도구 바인딩 (tool calling)** — 도구 시스템 Phase 의 본질. Phase 2 호출 어댑터에는 도구 인자 시그니처를 박지 않는다.
6. **에러 envelope (`{ok, error, hint, retryable}`)** — 도구 베이스 Phase 에서 본격 다룸. Phase 2 는 SDK 예외를 그대로 전파하거나 최소 래핑만.
7. **성능 NFR (응답 시간 / 처리량 목표)** — Phase 1 동일 원칙으로 over-engineering 회피. 측정만 가능하면 됨.
8. **메트릭 backend 구현 (Prometheus / OpenTelemetry 등)** — FR-6 슬롯만 노출, 실제 backend 는 도메인 책임.

## 6. 수용 기준 (Acceptance Criteria)

- **AC-1**: `LLMClient` Protocol 이 `runtime_checkable` 로 정의되고, 미적합 클래스는 `isinstance(...)` 체크로 구분된다. (FR-1)
- **AC-2**: Gemini 어댑터 인스턴스가 `isinstance(client, LLMClient) is True`. (FR-2)
- **AC-3**: `render(ctx)` 출력이 Gemini 메시지 구조로 변환될 때 boundary 위/아래가 별도 영역(예: system / user content) 으로 분리됨이 단위 테스트로 검증된다. (FR-3)
- **AC-4**: 동일 `ctx` 로 `await client.generate(...)` 두 번 호출 시 두 번째 호출에서 `CachedContent` 재사용이 발생함이 mock 또는 replay 테스트로 GREEN 검증된다. (FR-4)
- **AC-5**: `CachePolicy(ttl=..., enabled=False, force_invalidate=True)` 등의 컨트롤이 단위 테스트로 정상 동작함이 검증된다. (FR-5)
- **AC-6**: 캐시 적중·미적중 카운터가 누적되고, observer 등록 후 호출 시 callback 이 정확한 이벤트(hit / miss / hash-change) 로 호출됨이 단위 테스트로 검증된다. (FR-6)
- **AC-7**: 동일 `ctx` → 동일 cache key, N=10 회 반복 안정. (NFR-3)
- **AC-8**: `best_agent_base/llm/__init__.py` 가 AST 검증(Phase 1 `test_init_purity.py` 패턴 확장) 으로 docstring-only 유지됨이 자동 확인된다. (NFR-2)
- **AC-9**: `tests/test_no_domain_vocab.py` 의 FORBIDDEN_TERMS 가 `best_agent_base/llm/` 트리 전체에서 regex grep 0 건. (NFR-1)
- **AC-10**: 모든 FR 단위 테스트 + 캐시 적중 통합 테스트 GREEN, `uv run ruff check .` clean. (NFR-4)
- **AC-11**: AnthropicClient 인스턴스가 `isinstance(client, LLMClient) is True` (FR-7)
- **AC-12**: Anthropic 통합 테스트 — 동일 `ctx` 두 번 호출 시 두 번째 호출의 system message 에 `cache_control: {"type": "ephemeral"}` marker 가 동일 위치 부착되고 mock 응답의 `usage.cache_read_input_tokens > 0` 시뮬레이션이 검증됨 (FR-7)

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 19:27] [요구사항-수정]
- **id**: CH-20260503-001
- **이유**: 신규 피처 brainstorming 결과 (Phase 2 LLM 클라이언트 통합 — 본래 "KV 캐싱 단독 Phase" 였던 항목을 호출 레이어 흡수 결정)
- **무엇이**: phase-2-llm-client-requirements.md 전체 (§1 배경/목적, §2 사용자 스토리 US-1..3, §3 FR-1..6, §4 NFR-1..4, §5 OOS 8항목, §6 AC-1..10)
- **영향범위**: 없음 (최초 생성)

### [2026-05-03 20:26] [요구사항-수정]
- **id**: CH-20260503-010
- **이유**: 사용자 결정 — 본래 OOS-1 ("Anthropic 어댑터 본 구현") 으로 분리됐던 항목을 본 Phase 2 범위에 포함. 이유: provider 추상화의 진정한 검증은 2개 어댑터를 같이 만들어야 가능 (Gemini `CachedContent` ↔ Anthropic `cache_control` ephemeral marker 두 메커니즘이 동일 `CachePolicy` 흐름으로 통합되는지 실증). 추상화 두려움 회피의 정확한 해법.
- **무엇이**: §1-(B) 본질 갱신 (얇은 추상화 + 2개 참조 구현으로 확장), §3 FR-7 신규 (Anthropic 어댑터), §5-1 OOS-1 retroactive 제거 (~~취소선~~ + cross-link), §6 AC-11/AC-12 신규
- **영향범위**: phase-2-llm-client-tech-design.md (§2 영향 컴포넌트에 anthropic.py 추가 / §5 D7 신규 결정 필요 / §6 R-7 신규 위험 / §7 테스트 추가), phase-2-llm-client-implementation-plan.md (Task 6.5 신규 — Anthropic 어댑터 + 통합 테스트), TODO.md (Phase 2 정의 갱신)
- **연관 항목**: CH-20260503-001 (PRD 최초), CH-20260503-002 (tech-design — D7 추가 cascade 대상), CH-20260503-003 (plan — Task 6.5 추가 cascade 대상)
