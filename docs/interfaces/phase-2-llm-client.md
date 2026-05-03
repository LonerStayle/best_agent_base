# LLM 클라이언트 통합 (캐싱 흡수) — 인터페이스 가이드

## 1. 모듈 책임

**Phase 1 의 시스템 프롬프트 정적/동적 분리 출력을 실제 LLM 호출까지 도달시키는 종단 경로 + 두 provider (Gemini / Anthropic) 의 KV 캐싱을 통합 인터페이스로 흡수**.

---

## 2. 사용 예시

### 2.1 Gemini 단일 호출 (가장 흔한 use case)

```python
import asyncio
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def main():
    client = GeminiClient()  # 디폴트 = DEFAULT_CHAT 프로파일 (FLASH)
    resp = await client.generate(RenderContext())
    print(resp.text)
    print(f"cache_hit={resp.cache_hit} static_hash={resp.static_hash}")
    print(f"input={resp.usage.input_tokens} output={resp.usage.output_tokens}")


asyncio.run(main())
```

두 번째 호출부터 정적부 (BOUNDARY 위) 가 자동으로 Gemini `CachedContent` 로 재사용 → `cache_hit=True`.

### 2.2 Anthropic 으로 갈아끼우기 — 호출 코드 1줄만 변경

```python
from best_agent_base.llm.anthropic import AnthropicClient

client = AnthropicClient()  # 디폴트 model=claude-sonnet-4-5-20250929
resp = await client.generate(RenderContext())
# 동일한 LLMResponse(text, static_hash, cache_hit, usage) 반환
# Anthropic 은 system 메시지 cache_control: ephemeral marker 자동 부착
```

같은 `LLMClient` Protocol + 같은 `CachePolicy` + 같은 `LLMResponse` — provider 차이 모름.

### 2.3 캐시 정책 컨트롤 + 메트릭 observer 등록

```python
from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.gemini import GeminiClient

metrics = CacheMetrics()
metrics.add_observer(lambda ev, h: print(f"[{ev.value}] hash={h[:8]}"))
client = GeminiClient(metrics=metrics)

# 캐시 비활성
resp = await client.generate(RenderContext(), cache_policy=CachePolicy(enabled=False))

# 강제 무효화 (기존 캐시 버리고 새로)
resp = await client.generate(RenderContext(), cache_policy=CachePolicy(force_invalidate=True))

# TTL 변경 (기본 3600s)
resp = await client.generate(RenderContext(), cache_policy=CachePolicy(ttl_seconds=600))

print(metrics.stats())  # {"hit": N, "miss": M, "hash_change": K}
```

### 2.4 도메인 어댑터 등록 — 새 provider 끼우기 (Open/Closed)

```python
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient, LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


class MyVLLMClient:
    """사내 vLLM 호스팅 어댑터."""

    async def generate(
        self, ctx: RenderContext, *, cache_policy: CachePolicy | None = None
    ) -> LLMResponse:
        # ... vLLM API 호출 ...
        return LLMResponse(
            text="...",
            static_hash="...",
            cache_hit=False,
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )

    def count_tokens(self, text: str) -> int:
        return len(text.split())


client: LLMClient = MyVLLMClient()
assert isinstance(client, LLMClient)  # runtime_checkable
```

베이스 코드 0 줄 수정. `LLMClient` 적합 클래스를 만들면 끝.

---

## 3. 핵심 개념

```
┌────────────────────────────────────────────────────────────────────┐
│                      도메인 호출자                                  │
│   resp = await client.generate(ctx, cache_policy=policy)          │
└──────────────────────┬─────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────────────────┐
│  LLMClient Protocol (runtime_checkable, B-thin)                    │
│  - async generate(ctx, *, cache_policy) → LLMResponse              │
│  - count_tokens(text) → int                                        │
└──────┬─────────────────────────────────────────────────┬───────────┘
       ↓                                                 ↓
┌────────────────────────┐                ┌──────────────────────────┐
│  GeminiClient          │                │  AnthropicClient         │
│  - google-genai 직접    │                │  - anthropic SDK 직접     │
│  - in-memory cache_map │                │  - server-side hash      │
│  - asyncio.Lock per    │                │  - cache_control:        │
│    static_hash (R-1)   │                │    ephemeral marker      │
│  - try/except → None   │                │    on last system block  │
│    fallback (D6)       │                │  - SDK 예외 그대로 전파    │
└──────┬─────────────────┘                └──────────────────┬───────┘
       │                                                     │
       └──────────────────┬──────────────────────────────────┘
                          ↓
        ┌─────────────────────────────────┐
        │  공통 인터페이스 + 흐름           │
        │  - CachePolicy (frozen)         │
        │    enabled / ttl_seconds /      │
        │    force_invalidate             │
        │  - CacheMetrics + observers     │
        │  - LLMResponse (frozen)         │
        │    text / static_hash /         │
        │    cache_hit / usage            │
        └────────────┬────────────────────┘
                     ↑
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1 (시스템 프롬프트 — 캐시 친화 슬롯)                            │
│  render(ctx) → "<static>\n\n__BOUNDARY__\n\n<dynamic>"              │
│  get_static_hash(ctx) → sha256[:16]   ← 캐시 키 단일 진실원천         │
└─────────────────────────────────────────────────────────────────────┘
```

**provider 메커니즘 차이 — 같은 인터페이스로 흡수**:

| 항목 | Gemini | Anthropic |
|---|---|---|
| 캐시 단위 | `CachedContent` 객체 (server resource, name 으로 재호출) | system text block 의 inline marker (요청마다 송신, server hash 매칭) |
| TTL | `CreateCachedContentConfig(ttl="3600s")` 명시 | ephemeral = 5min default (`ttl_seconds` 는 ephemeral 한 종류로만 매핑) |
| 적중 신호 | `usage.cached_content_token_count > 0` | `usage.cache_read_input_tokens > 0` |
| 키 derivation | client-side `static_hash` → `caches.create()` | server-side hash, 동일 system text 만 보내면 됨 |
| `force_invalidate=True` | in-memory map 에서 hash 제거 + 새 `caches.create` | marker 미부착 (= `enabled=False` 와 동일 효과) |

---

## 4. 확장 포인트

### 4.1 `LLMClient` Protocol 구현으로 새 provider 어댑터 등록

`@runtime_checkable Protocol` — method 존재만 검증 (시그니처는 mypy/ty 정적 체크 위임). `generate` (async) + `count_tokens` 두 메서드만 구현.

```python
class MyClient:
    async def generate(self, ctx, *, cache_policy=None) -> LLMResponse: ...
    def count_tokens(self, text: str) -> int: ...

assert isinstance(MyClient(), LLMClient)  # True
```

### 4.2 `CacheMetrics` observer 등록으로 메트릭 backend 연결

```python
metrics = CacheMetrics()
metrics.add_observer(prometheus_export)  # callable 만 보장하면 됨
metrics.add_observer(structlog_logger)
client = GeminiClient(metrics=metrics)
```

### 4.3 `CachePolicy` 도메인 정책 클래스 (확장)

`CachePolicy` 는 frozen Pydantic. 도메인이 자기 정책 (예: 시간대별 다른 TTL, 사용자 그룹별 enabled) 만들고 싶으면 별도 BaseModel + 변환 함수.

### 4.4 금지 사항

- ❌ `CacheMetrics.observer` 에 무거운 동기 작업 (HTTP 호출, DB write 등). 베이스는 fire-and-forget 동기 emit. 무거운 backend 가 필요하면 도메인 observer 안에서 `asyncio.create_task()` 로 분리.
- ❌ 베이스에 영속 cache backend 추가 (Redis / SQLAlchemy). 베이스는 in-memory dict 만. 영속 필요 시 도메인이 자기 storage 매핑.
- ❌ `LLMResponse` 에 에러 envelope (`{ok, error, hint, retryable}`) 흡수. SDK 예외 그대로 전파 — envelope 는 도구 시스템 phase 의 본질.
- ❌ 베이스에서 streaming / 도구 바인딩 시그니처 추가. 후속 phase 의 별도 Protocol.

---

## 5. 위험·주의사항

도메인 사용자가 알아야 할 것 (내부 R-id 그대로 노출 — `<slug>-tech-design.md §6` 참조):

- **R-1 race**: `GeminiClient` 의 `_get_or_create_cached_content` 는 `asyncio.Lock` per static_hash 로 동시 호출에서 단일 `caches.create` 보장. 도메인이 별도 mutex 추가 불필요.
- **R-2 perf**: cache miss 첫 호출은 `caches.create` + `generate_content` 두 RTT 가능. 두 번째 호출부터 적중. Anthropic 은 server-side hash 라 RTT 1 회 그대로.
- **R-4 side-effect**: 정적부 (`render(ctx)` 의 BOUNDARY 위) 가 미세 변동하면 (`@[MODEL: ...]` 마커 누적 등) hash 변동 → 캐시 자동 무효화. `CacheEvent.HASH_CHANGE` emit 으로 도메인이 가시성 확보.
- **R-5 perf (observer)**: observer 는 가벼워야 함. 무거우면 도메인이 자기 task 분리.
- **R-7 side-effect (Anthropic)**: `cache_control` marker 가 system 메시지의 마지막 text block 에 정확히 부착돼야 server-side hash 매칭. 베이스 코드 single-point fix 라 도메인이 직접 marker 만지지 말 것.

**메트릭 계약 — 중요**:
> `HASH_CHANGE` 는 같은 호출 안에서 후속 `MISS` 와 union 으로 발생하는 **causal annotation**. 도메인 observer 측에서 `HASH_CHANGE + MISS` 를 합산하면 cache 압력 overcount. `HIT / MISS` 만으로 적중률 계산.

**`force_invalidate=True` semantic 차이**:
- Gemini: in-memory map 에서 hash 제거 + 새 `caches.create` (RTT 1 회 추가)
- Anthropic: server-side invalidate API 없음. marker 미부착 (= `enabled=False` 와 동일 효과). 다음 호출 시 자동으로 new cache 생성

---

## 6. 다른 모듈과의 연계

- **시스템 프롬프트 모듈**: 본 모듈의 `static_hash` 캐시 키 = 시스템 프롬프트 모듈의 `get_static_hash(ctx)`. 정적부 결정성이 본 모듈의 캐시 적중률 source of truth.
- **도구 시스템 (후속)**: 도구 카탈로그 자체도 정적/동적 분리 예정. always-load 도구 = 정적부 (캐시 대상), deferred 도구 = 동적부. 본 모듈의 boundary split 헬퍼 (`split_at_boundary`) 가 도구 description 도 boundary 기준으로 split.
- **컨텍스트 관리 (후속)**: `count_tokens` 가 현재 placeholder (`int(words * 1.3)`). 컨텍스트 관리 단계에서 SDK 의 정확한 count API (`client.models.count_tokens` / `client.messages.count_tokens`) 로 교체 예정.
- **Hooks 시스템 (후속)**: `PreModelCall` / `PostModelCall` 훅이 추가되면 본 모듈의 `generate` 가 그 훅 발동 지점.
- **API 노출 (FastAPI)**: 본 모듈이 노출하는 비동기 `generate` 가 FastAPI 의 streaming endpoint 의 진입점.

---

## 7. 데모 노트북 / 참조 코드

- **데모 노트북**: [`notebooks/phase-2-llm-client-demo.ipynb`](../../notebooks/phase-2-llm-client-demo.ipynb) (산출물 룰 4부 골격)
- **참조 코드**:
  - `best_agent_base/llm/gemini.py` — Gemini 어댑터 본체
  - `best_agent_base/llm/anthropic.py` — Anthropic 어댑터 본체
  - `best_agent_base/llm/messages.py` — boundary split 헬퍼
  - `tests/test_gemini_adapter.py` — race / cache hit/miss / force_invalidate 검증
  - `tests/test_anthropic_adapter.py` — cache_control marker 위치 회귀
  - `main.py` — 단순 호출 데모

---

## 8. Public API (Reference)

import 룰: 각 심볼은 풀 경로로 import (`best_agent_base.llm.<module>`). `best_agent_base/llm/__init__.py` 는 docstring-only (D-13) — 재수출 안 함, 도메인이 명시적으로 import.

### `best_agent_base.llm.client`

```python
from typing import Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.prompts.render import RenderContext


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    static_hash: str
    cache_hit: bool
    usage: TokenUsage


@runtime_checkable
class LLMClient(Protocol):
    """Provider-agnostic LLM 호출 슬롯 (B-thin).

    runtime_checkable 는 method 존재만 체크. 시그니처 정확성은 mypy/ty 정적 체크에 위임.
    """

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse: ...

    def count_tokens(self, text: str) -> int: ...
```

### `best_agent_base.llm.cache_policy`

```python
from pydantic import BaseModel, ConfigDict, Field


class CachePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    ttl_seconds: int = Field(default=3600, gt=0)
    force_invalidate: bool = False
```

### `best_agent_base.llm.cache_metrics`

```python
from collections.abc import Callable
from enum import StrEnum


class CacheEvent(StrEnum):
    HIT = "hit"
    MISS = "miss"
    HASH_CHANGE = "hash_change"


CacheObserver = Callable[[CacheEvent, str], None]
"""(event, static_hash) → None. 동기 callable, 가볍게."""


class CacheMetrics:
    def __init__(self) -> None: ...
    def add_observer(self, observer: CacheObserver) -> None: ...
    def emit(self, event: CacheEvent, static_hash: str) -> None: ...
    def stats(self) -> dict[str, int]: ...
```

### `best_agent_base.llm.messages`

```python
from best_agent_base.prompts.render import RenderContext


def split_at_boundary(ctx: RenderContext) -> tuple[str, str]:
    """Returns (static_text, dynamic_text), split at SYSTEM_PROMPT_DYNAMIC_BOUNDARY.

    provider-agnostic — Gemini / Anthropic 어댑터 모두 동일 split 재사용.
    """
```

### `best_agent_base.llm.gemini`

```python
from best_agent_base.llm.cache_metrics import CacheMetrics
from best_agent_base.llm.profiles import DEFAULT_CHAT, ModelProfile


class GeminiClient:  # implements LLMClient
    def __init__(
        self,
        profile: ModelProfile = DEFAULT_CHAT,
        *,
        metrics: CacheMetrics | None = None,
    ) -> None: ...
```

### `best_agent_base.llm.anthropic`

```python
from best_agent_base.llm.cache_metrics import CacheMetrics


class AnthropicClient:  # implements LLMClient
    def __init__(
        self,
        *,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        metrics: CacheMetrics | None = None,
    ) -> None: ...
```

### 환경 변수

- `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY` — `GeminiClient` 인스턴스화 시 필수
- `ANTHROPIC_API_KEY` — `AnthropicClient` 인스턴스화 시 필수
- `python-dotenv` 의 `load_dotenv()` 로 `.env` 자동 로딩 가능 (`main.py` 참조)
