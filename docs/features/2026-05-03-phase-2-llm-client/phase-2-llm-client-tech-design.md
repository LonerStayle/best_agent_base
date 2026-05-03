# 개발방향: LLM 클라이언트 통합 (캐싱 흡수)

> **For agentic workers:** This document is the technical spec (architecture, components, data, interfaces, decisions, risks, test strategy). It is anchored to `phase-2-llm-client-requirements.md` (the PRD) and consumed by `phase-2-llm-client-implementation-plan.md` (step-by-step plan). NEXT STEP: invoke `writing-plans` skill (or run `/write-plan`) to produce `phase-2-llm-client-implementation-plan.md` from this design. Do NOT include step-by-step implementation tasks here — those belong in the plan.

## 1. 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Domain Project                                │
│   client = GeminiClient(profile=DEFAULT_CHAT, metrics=metrics)       │
│   resp = await client.generate(ctx, cache_policy=CachePolicy(...))   │
└────────────────────────────┬─────────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────────┐
│  best_agent_base/llm/  (Phase 2 신규)                                 │
│                                                                      │
│  ┌─────────────────┐    ┌──────────────────┐   ┌──────────────────┐  │
│  │ LLMClient       │←───│ GeminiClient     │←──│ google.genai     │  │
│  │ (Protocol,      │    │ (참조 구현)       │   │ Client (직접)    │  │
│  │ runtime_check)  │    │                  │   │                  │  │
│  └─────────────────┘    └────────┬─────────┘   └──────────────────┘  │
│                                  │                                   │
│  ┌──────────────┐   ┌────────────┴────────┐   ┌────────────────┐    │
│  │ CachePolicy  │──→│ build_gemini_msgs() │──→│ CachedContent  │    │
│  │ (frozen)     │   │ (static, dynamic)   │   │ (key=hash)     │    │
│  └──────────────┘   └─────────────────────┘   └────────┬───────┘    │
│                                  ↑                     │            │
│                                  │            ┌────────┴───────┐    │
│  ┌──────────────┐         ┌──────┴──────┐    │ CacheMetrics    │    │
│  │ LLMResponse  │←────────│ generate()  │────│ observer emit   │    │
│  │ (frozen)     │         │ flow        │    │ (hit/miss/      │    │
│  └──────────────┘         └─────────────┘    │  hash_change)   │    │
│                                              └─────────────────┘    │
└────────────────────────────┬─────────────────────────────────────────┘
                             ↑
┌──────────────────────────────────────────────────────────────────────┐
│  best_agent_base/prompts/  (Phase 1, 변경 없음)                       │
│  render(ctx) → "static\n\n__BOUNDARY__\n\ndynamic"                   │
│  get_static_hash(ctx) → sha256[:16]   ← cache key 의 source of truth │
└──────────────────────────────────────────────────────────────────────┘
```

**핵심 흐름** (단일 호출):
1. 도메인이 `await client.generate(ctx, cache_policy=...)` 호출.
2. `build_gemini_messages(ctx)` 가 Phase 1 `render(ctx)` 출력을 BOUNDARY 마커 기준 (static, dynamic) 으로 분리.
3. `cache_policy.enabled` 면 `get_static_hash(ctx)` 키로 in-memory map 조회:
   - 적중 + `force_invalidate=False` → 기존 `CachedContent` 재사용 + `CacheEvent.HIT` emit
   - 미적중 또는 `force_invalidate=True` → `client.aio.caches.create(...)` + map 등록 + `CacheEvent.MISS` emit
   - 이전 hash 와 다름 → `CacheEvent.HASH_CHANGE` emit (관찰용)
4. Gemini SDK 호출 → `LLMResponse(text, static_hash, cache_hit, usage)` 반환.

**SDK 결정**: `google.genai` (Google GenAI SDK 1급) 직접 사용. LangChain `langchain_google_genai` 는 베이스에서 제거 — `CachedContent` 가 LangChain 표준 추상이 아니어서 본 Phase 핵심 (KV 캐싱 컨트롤) 과 정합 불가. 결정 근거는 §5-D1 참조.

## 2. 영향 받는 컴포넌트/파일

### 신규 (Phase 2 추가)

| 파일 | 역할 | 매핑 FR |
|---|---|---|
| `best_agent_base/llm/client.py` | `LLMClient` Protocol + `LLMResponse` + `TokenUsage` (frozen) | FR-1 |
| `best_agent_base/llm/cache_policy.py` | `CachePolicy` frozen 모델 (enabled/ttl/force_invalidate) | FR-5 |
| `best_agent_base/llm/cache_metrics.py` | `CacheEvent(StrEnum)` + `CacheObserver` + `CacheMetrics` (observer registry) | FR-6 |
| `best_agent_base/llm/messages.py` | `build_gemini_messages(ctx)` — Phase 1 `render(ctx)` → (static, dynamic) split | FR-3 |
| `best_agent_base/llm/anthropic.py` | `AnthropicClient` 클래스 (LLMClient 적합) + `build_anthropic_messages(ctx, *, cache)` 헬퍼. `anthropic.AsyncAnthropic` 직접 사용. system 메시지 마지막 text block 에 `cache_control: {"type": "ephemeral"}` marker 부착으로 캐싱 (D7) | FR-7 |

### 변경 (Phase 0 1차 골격 위)

| 파일 | 변경 | 매핑 FR |
|---|---|---|
| `best_agent_base/llm/gemini.py` | LangChain → google-genai 직접 사용으로 재작성. `GeminiClient` 클래스 (LLMClient 적합) + 기존 `get_gemini()` 는 deprecated 또는 thin wrapper | FR-2, FR-4 |
| `best_agent_base/llm/__init__.py` | docstring-only 유지 (NFR-2) — 본문 변경 없음, AST 검증만 확장 | NFR-2 |
| `pyproject.toml` | `langchain*` 제거, `google-genai>=1.0` + `anthropic>=0.40` 추가 (정확한 버전은 implementation 단계 context7 검증) | (deps) |
| `main.py` | `get_gemini()` → `GeminiClient(...)` 마이그레이션 또는 deprecated 데모 분리 (그루밍 노트 #2 동시 처리 후보) | (caller) |

### 신규 테스트 파일

| 파일 | 검증 대상 |
|---|---|
| `tests/test_llm_client_protocol.py` | LLMClient runtime_checkable 적합성 (AC-1, AC-2) |
| `tests/test_llm_messages.py` | `build_gemini_messages` boundary 분리 (AC-3) |
| `tests/test_cache_policy.py` | CachePolicy frozen / 디폴트 / 컨트롤 필드 (AC-5) |
| `tests/test_cache_metrics.py` | observer 등록·이벤트 emit (AC-6) |
| `tests/test_gemini_adapter.py` | GeminiClient (mock SDK) — generate 흐름 + cache hit/miss (AC-2, AC-4) |
| `tests/test_cache_key_stability.py` | 동일 ctx → 동일 cache key, N=10 (AC-7) |
| `tests/test_anthropic_adapter.py` | AnthropicClient (mock SDK) — generate 흐름 + cache_control marker 부착 + cache hit 시뮬레이션 (AC-11, AC-12) |

### 기존 테스트 확장

| 파일 | 확장 |
|---|---|
| `tests/test_init_purity.py` | `best_agent_base/llm/__init__.py` AST 검증 추가 (AC-8) |
| `tests/test_no_domain_vocab.py` | `best_agent_base/llm/` 트리 regex grep 대상 추가 (AC-9) |

## 3. 데이터 모델/스키마 변경

**DB 스키마 변경 없음**. 본 Phase 의 캐시 매핑은 베이스에서 **in-memory dict**(`hash → cached_content_name`) 로만 관리. 프로세스 재시작 시 휘발 — 영속화는 도메인 책임 (Redis / SQLAlchemy 등 임의 backend, FR-6 메트릭 observer 와 별개).

**Pydantic 모델** (모두 `frozen=True`):

```python
class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0  # cache hit 시 input_tokens 중 캐시에서 충당된 부분

class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    static_hash: str        # 호출 시점 cache key (NFR-3 검증 source)
    cache_hit: bool
    usage: TokenUsage

class CachePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    ttl_seconds: int = 3600
    force_invalidate: bool = False
```

## 4. 외부 인터페이스

**Public API** (Phase 종료 시 `docs/interfaces/phase-2-llm-client.md` 산출 대상):

```python
# best_agent_base/llm/client.py
@runtime_checkable
class LLMClient(Protocol):
    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse: ...

    def count_tokens(self, text: str) -> int: ...  # FR-1 슬롯 only — Phase 9 본격

# best_agent_base/llm/gemini.py
class GeminiClient:  # implements LLMClient
    def __init__(
        self,
        profile: ModelProfile = DEFAULT_CHAT,
        *,
        metrics: CacheMetrics | None = None,
    ) -> None: ...

# best_agent_base/llm/cache_metrics.py
class CacheEvent(StrEnum):
    HIT = "hit"
    MISS = "miss"
    HASH_CHANGE = "hash_change"

CacheObserver = Callable[[CacheEvent, str], None]  # (event, static_hash)

class CacheMetrics:
    def add_observer(self, observer: CacheObserver) -> None: ...
    def emit(self, event: CacheEvent, static_hash: str) -> None: ...
    def stats(self) -> dict[str, int]: ...  # 누적 카운터 ({"hit": N, "miss": M, ...})

# best_agent_base/llm/messages.py
def build_gemini_messages(ctx: RenderContext) -> tuple[str, str]:
    """Returns (static_text, dynamic_text), split at SYSTEM_PROMPT_DYNAMIC_BOUNDARY."""
```

**HTTP/이벤트 IF 없음**. Phase 14 (FastAPI 노출) 에서 본격.

## 5. 핵심 결정 + 대안 비교

### D1. SDK 선택: google-genai 직접 (vs LangChain 유지 vs 하이브리드)

**선택**: google-genai 직접 (`from google import genai`). LangChain 의존 베이스에서 제거.

**대안**:
- (LangChain 유지) `langchain_google_genai.ChatGoogleGenerativeAI` 위에 어댑터. — `CachedContent` 가 LangChain 표준이 아니라 우회 필요. 본 Phase 핵심 (FR-4, FR-5) 와 정합 불가.
- (하이브리드) 두 SDK 공존. — deps 누적 + 도메인 혼란.

**근거**: Phase 2 의 본질이 "KV 캐싱 유지·컨트롤". `CachedContent` 가 google-genai 의 1급 기능이라 직접 사용이 가장 자연스러움. Phase 1 패턴 (provider 의 1급 기능 적나라 노출) 과도 일관.

### D2. LLMClient Protocol 시그니처 폭

**선택**: 얇은 Protocol — `async generate(ctx, *, cache_policy=None)` + `count_tokens(text)` 슬롯. (B-thin)

**대안**:
- (Wide Protocol) `generate_stream`, `bind_tools`, `with_retry` 등 다 포함. — PRD §5 OOS-4,5 와 충돌. YAGNI.
- (No Protocol, 함수만) `async def generate(client, ctx, ...)`. — D-8 (교체·확장 가능성) 슬롯 약화.

**근거**: PRD §1 B-thin 합의. 미래 메서드 (streaming/tool-binding) 는 후속 Phase 에서 Protocol 확장 또는 별도 Protocol (예: `StreamingLLMClient`) 로.

### D3. CachePolicy 컨트롤 항목

**선택**: `enabled` (on/off) + `ttl_seconds` + `force_invalidate` 3 개.

**대안**:
- (필드 추가) cache key prefix, max_cache_count, eviction_policy 등. — PRD AC-5 가 명시한 "TTL/on-off/강제 무효화" 외엔 YAGNI.
- (생략) `bool` 한 개 (캐시 on/off). — FR-5 "TTL/강제 무효화 컨트롤" 충족 못함.

**근거**: AC-5 의 검증 항목 (`ttl=...`, `enabled=False`, `force_invalidate=True`) 을 정확히 매핑. 추가 필드는 도메인이 자기 정책 클래스 만들어 변환.

### D4. 캐시 매핑 영속성

**선택**: in-memory dict 만 (프로세스 휘발).

**대안**:
- (영속 backend 베이스 제공) Redis/SQLAlchemy 어댑터 베이스에. — D-2 ("안 만들기") 위반. 도메인이 자기 storage 가짐.
- (파일 기반 캐시) JSON pickle 등. — race·side-effect 위험 + 도메인 책임 영역.

**근거**: 베이스 책임 = 인터페이스 + 메모리 참조 구현 1개. 영속화는 도메인이 `CacheMetrics` observer 와 결합해 자기 storage 에 매핑.

### D5. 메트릭 observer 동기 vs 비동기

**선택**: 동기 callable (`Callable[[CacheEvent, str], None]`).

**대안**:
- (비동기 callable) `Awaitable[None]`. — 호출 path 가 await 추가됨. 베이스 단순성 ↓.
- (이벤트 큐) asyncio.Queue. — D-2 위반. 도메인이 자기 큐 만들 수 있음.

**근거**: observer 자체가 무겁다는 건 도메인 책임 (Phase 2 §6 R-5 참조). 베이스는 fire-and-forget 동기 emit, 도메인 observer 가 무거우면 자기 안에서 task 분리.

### D7. Anthropic 캐싱 메커니즘 매핑 (Gemini ↔ Anthropic 통합 인터페이스)

**선택**: Anthropic 의 `cache_control: {"type": "ephemeral"}` marker 를 system 메시지의 마지막 text block 에 부착하는 방식. `LLMClient.generate(ctx, *, cache_policy)` 흐름 안에 흡수해 도메인은 provider 차이 모름.

**메커니즘 차이**:
| 항목 | Gemini | Anthropic |
|---|---|---|
| 캐싱 단위 | `CachedContent` 객체 (server-side resource, name 으로 재호출) | system message text block 에 inline marker (요청마다 송신, server 가 hash 매칭으로 자동 hit) |
| TTL | `CreateCachedContentConfig(ttl="...s")` 명시 | ephemeral = 5min default (1h 도 옵션) — `cache_policy.ttl_seconds` 를 ephemeral type 으로만 매핑 (2 옵션 중 가까운 것 선택) |
| 적중 신호 | `usage.cached_content_token_count > 0` | `usage.cache_read_input_tokens > 0` (생성은 `cache_creation_input_tokens > 0`) |
| 키 derivation | client-side `static_hash` → `caches.create()` → name 캐싱 | server-side hash, client 는 동일 system text 만 보내면 됨 |

**통합 흡수 방식**:
- `LLMClient.generate(ctx, *, cache_policy)` 시그니처는 두 어댑터 공통
- `cache_policy.enabled=False` → Gemini 는 `caches.create` skip + system_instruction 직접, Anthropic 은 `cache_control` marker 미부착
- `cache_policy.force_invalidate=True` → Gemini 는 in-memory map 에서 hash 제거 후 새 caches.create, Anthropic 은 invalidate 개념 없음 (server-side automatic) — marker 만 부착하고 marker 위치 변경(예: nonce 추가)으로 hash mismatch 유도 또는 OOS-of-current-task 로 두고 도메인이 `cache_policy.enabled=False` 한 번 호출로 우회
- 적중 결정: 두 어댑터 모두 응답의 usage 필드 보고 `LLMResponse.cache_hit` 채움 (Gemini = `cached_content_token_count > 0`, Anthropic = `cache_read_input_tokens > 0`)

**대안**:
- (Anthropic 캐싱 제외) FR-7 = 어댑터만, 캐싱은 Gemini 만. — 본 Phase 의 본질("KV 캐싱 유지·컨트롤") 을 Anthropic 에서 검증 못함. 통합 인터페이스 검증 실패.
- (extended cache 사용) Anthropic 의 1h cache type 사용. — `cache_policy.ttl_seconds >= 3600` 일 때만 1h, 미만은 ephemeral 로 자동 매핑 가능. 단 implementation 복잡도 ↑, Phase 2 는 ephemeral 한 종류로 단순화. 1h 매핑은 후속 그루밍.

**근거**: 두 SDK 의 1급 캐싱 메커니즘 둘 다 `LLMClient + CachePolicy` 1개 인터페이스로 흡수 가능함을 실증. PRD §1-(B) "통합 인터페이스로 흡수" 의 정확한 검증.

### D6. SDK 예외 처리 정책

**선택**: google-genai SDK 의 예외 (예: `google.genai.errors.APIError`, `ServerError`, `ClientError`) 를 **그대로 전파**. 베이스에서 envelope (`{ok, error, hint, retryable}`) 변환하지 않음.

**대안**:
- (envelope 변환) Phase 2 에서 `LLMResponse(ok=False, error=..., retryable=...)` 형태로 흡수. — PRD §5 OOS-6 와 충돌 (envelope 는 도구 베이스 Phase 의 본질). 도구 시스템 시그니처 결정 전에 미리 모델링하면 후일 변경 비용↑.
- (최소 래핑만) `LLMClientError(BaseException)` 같은 커스텀 예외로 한 단계만 wrap. — 도메인이 SDK 예외 타입을 직접 알 필요는 줄지만, 정보 손실 + Phase 4 envelope 와 또 다른 추상 추가 위험.

**근거**: PRD OOS-6 명시. Phase 2 는 호출 레이어만 깔고, 에러 의미론(retryable / hint / fallback 정책)은 도구 베이스 Phase 에서 envelope 와 함께 한꺼번에 결정. 단 implementation 단계에서 SDK 예외가 cache_policy 분기 (특히 cache 생성 실패) 안으로 새지 않도록 try/except 경계만 명시 — 캐시 실패는 캐시 우회 + miss event emit 후 일반 호출로 fallback (캐시 가용성과 호출 가용성 분리).

## 6. 위험/사이드이펙트 (preliminary)

| id | 카테고리 | 상황 | 완화 |
|---|---|---|---|
| **R-1** | race | 동시 호출에서 동일 hash 의 `CachedContent` 가 중복 생성될 수 있음 (첫 요청이 cache 만들기 전에 두 번째 요청이 또 만들려 시도) | 베이스에 `asyncio.Lock` per static_hash 또는 단일 mutex. implementation 단계에서 mock 으로 race 시나리오 단위 테스트. |
| **R-2** | perf | cache miss 첫 호출은 (a) `caches.create()` + (b) `generate()` 두 번 RTT 발생 가능 | google-genai SDK 가 한 번에 처리하는지 확인 필요. 안 되면 첫 호출 비용은 trade-off 로 받아들임 (정상 동작). 두 번째 호출부터 적중 — AC-4 의 "두 번째 호출에서 적중" 검증으로 충분. |
| **R-3** | breaking | LangChain 제거 → `main.py` 의 `get_gemini()` + `langgraph` demo 깨짐 | (a) `main.py` 도 google-genai 로 재작성 (그루밍 노트 #2 동시 처리), 또는 (b) `main.py` 를 deprecated 마크 + `examples/legacy_langchain_demo.py` 로 이동. implementation 단계 결정. |
| **R-4** | side-effect | `static` 섹션에 `@[MODEL: ...]` 마커 누적 → hash 변동 → 캐시 자동 무효화 | 의도된 동작. 단 운영 가시성을 위해 `CacheEvent.HASH_CHANGE` emit 으로 도메인이 추적 가능. |
| **R-5** | perf | metric observer 가 동기 callable — oversized observer (예: 동기 HTTP write) 가 호출 path 지연 | 베이스 정책 명문화 — observer 는 가벼워야 함 (도메인 인터페이스 가이드에 명시). 도메인이 무거운 backend 쓰려면 자기 안에서 task 분리. |
| **R-6** | breaking | `CachePolicy` frozen 모델에 향후 필드 추가 시 호환성 | Pydantic default 값 + `model_config = ConfigDict(frozen=True, extra="ignore")` 검토. 도메인이 자기 정책 클래스 만들 수 있는 슬롯 (`CachePolicy` 상속 또는 변환). |
| **R-7** | side-effect | Anthropic `cache_control` marker 가 system 메시지의 마지막 text block 에 부착돼야 적중. block 순서가 흔들리거나 `static_text` 가 미세 변동 시 자동 cache miss (server-side hash mismatch) | Phase 1 `get_static_hash` 가 결정성 보장 (NFR-3) 하므로 동일 ctx → 동일 system_text → 동일 cache hit. marker 부착 위치는 어댑터 코드에서 single point (last text block) 으로 고정. test_anthropic_adapter.py 가 marker 위치·구조 단위 회귀 잡음. |

## 7. 테스트 전략

### 단위 테스트 (각 FR 매핑)

- **FR-1 → AC-1, AC-2**: `tests/test_llm_client_protocol.py` — Protocol runtime_checkable, isinstance 체크 (적합/미적합 케이스)
- **FR-2 → AC-2**: `tests/test_gemini_adapter.py` — GeminiClient 인스턴스 isinstance 검증
- **FR-3 → AC-3**: `tests/test_llm_messages.py` — `build_gemini_messages(ctx)` 가 boundary 위/아래 정확히 split
- **FR-4 → AC-4**: `tests/test_gemini_adapter.py` — Gemini SDK mock, 동일 ctx 두 번 호출 → 두 번째 cache hit 검증
- **FR-5 → AC-5**: `tests/test_cache_policy.py` — frozen 검증, `enabled=False` 시 캐시 우회, `force_invalidate=True` 시 새 cache 생성
- **FR-6 → AC-6**: `tests/test_cache_metrics.py` — observer 등록, emit 시 callback 호출 + 카운터 누적

### 회귀·invariant

- **AC-7**: `tests/test_cache_key_stability.py` — 동일 ctx N=10 회 hash 동일 (NFR-3)
- **AC-8**: `tests/test_init_purity.py` 확장 — `llm/__init__.py` AST docstring-only (NFR-2)
- **AC-9**: `tests/test_no_domain_vocab.py` 확장 — `best_agent_base/llm/` 트리 regex 0건 (NFR-1)

### 통합

- **AC-4** 의 캐시 적중 검증 = SDK mock (record/replay) 로 충분. 실제 Gemini API 호출은 통합 테스트 환경에 두지 않음 (deps + 비용 + 결정성). — `pytest -m integration` 으로 분리, 실제 키 있을 때만 수동 실행.

### CI / 정합성

- **AC-10**: `uv run pytest -v && uv run ruff check .` 모두 GREEN. Phase 1 패턴 일관 적용.

### 격리·conftest

- Phase 1 의 `restore_registry` snapshot/restore 패턴이 4 파일에서 중복 → Phase 2 진입 시점에 `tests/conftest.py` 도입 후보 (그루밍 노트 #3). Phase 2 신규 테스트도 `CacheMetrics` 인스턴스 격리가 필요할 가능성 — autouse `cache_metrics_isolation` fixture 도 동시 도입.

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 19:36] [개발방향-수정]
- **id**: CH-20260503-002
- **이유**: 신규 기술 설계 (designing-direction). PRD CH-20260503-001 의 FR-1..6, NFR-1..4, OOS 8 항목, AC-1..10 을 §1 아키텍처 / §2 영향 컴포넌트 8 / §3 데이터 모델 (frozen 3) / §4 Public API / §5 핵심 결정 D1..D6 / §6 위험 R-1..6 / §7 테스트 8 로 매핑. verifying-spec 보고서 권장 1번 (OOS-6 SDK 예외 처리 정책) 반영해 D6 추가.
- **무엇이**: phase-2-llm-client-tech-design.md 전체 (§1..§7 신규 작성 + §5-D6 권장 보완)
- **영향범위**: 없음 (최초 생성). 후속 영향 = phase-2-llm-client-implementation-plan.md (writing-plans 단계 시작 시 D1..D6 → task 매핑 + R-1..6 → 위험 코드 지점 매핑 필수)
- **연관 항목**: CH-20260503-001 (PRD)

### [2026-05-03 20:30] [개발방향-수정]
- **id**: CH-20260503-011
- **이유**: PRD CH-20260503-010 의 OOS-1 retroactive 제거 + FR-7 추가에 대한 cascade 갱신. tech-design 에 D7 (Anthropic 캐싱 메커니즘 매핑) + R-7 (cache_control marker 위치·구조 위험) + §2 영향 컴포넌트 (`anthropic.py`) + §7 테스트 (test_anthropic_adapter.py) 추가.
- **무엇이**: §2 영향 컴포넌트 표 (anthropic.py + test_anthropic_adapter.py 추가, pyproject.toml deps 항목에 anthropic 추가), §5 D7 신규 (Gemini ↔ Anthropic 캐싱 메커니즘 매핑 + 통합 흡수 방식), §6 R-7 신규 (Anthropic marker 위치 위험 + Phase 1 결정성 mitigation)
- **영향범위**: phase-2-llm-client-implementation-plan.md (Task 6.5 신규 — Anthropic 어댑터 task. context7 으로 anthropic SDK 정확 시그니처 확인 필수). 기존 Task 1 deps 는 이미 commit 됐지만 anthropic 추가는 Task 6.5 시점에 별도 commit 으로 추가 (uv add anthropic). 기존 Task 7 (NFR vocab scan llm/) 가 anthropic.py 도 자동 cover.
- **연관 항목**: CH-20260503-001 (PRD 최초), CH-20260503-002 (tech-design 최초), CH-20260503-010 (PRD FR-7 추가)
