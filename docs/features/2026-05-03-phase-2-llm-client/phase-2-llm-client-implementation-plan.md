# LLM 클라이언트 통합 (캐싱 흡수) 구현계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1 `render(ctx)` 출력을 실제 LLM 호출까지 도달시키는 종단 경로를 베이스화하면서 KV 캐싱(Gemini `CachedContent`) 을 1급 슬롯으로 통합·컨트롤·메트릭 노출한다.

**Architecture:** `best_agent_base/llm/` 트리에 4 신규 src (client / cache_policy / cache_metrics / messages) + 1 재작성 (gemini) 을 두고, `LLMClient` Protocol → `GeminiClient` (google-genai 직접) → `CachedContent` (key=`get_static_hash`) 흐름을 박는다. `pyproject.toml` deps 는 `langchain*` 제거 + `google-genai` 추가. `main.py` 는 `GeminiClient` 로 마이그레이션.

**Tech Stack:** Python 3.12 / Pydantic 2 (frozen) / `google-genai` SDK / asyncio (race lock) / pytest + Phase 1 패턴 (snapshot/restore fixture, AST/regex invariant)

**Spec inputs:**
- `phase-2-llm-client-requirements.md` — FR-1..6, NFR-1..4, OOS 8, AC-1..10 (CH-20260503-001)
- `phase-2-llm-client-tech-design.md` — D1 google-genai 직접 / D2 B-thin Protocol / D3 3-필드 CachePolicy / D4 in-memory map / D5 동기 observer / D6 SDK 예외 그대로 전파 (CH-20260503-002)

---

## 1. 단계별 작업

### Task 1: deps 교체 (pyproject.toml)

**Files:**
- Modify: `pyproject.toml` (dependencies 블록)
- Run: `uv sync`

이 task 는 코드 변경이 없는 구성 변경이라 TDD cycle 의 test 단계는 "기존 테스트 70개 GREEN 유지" 로 갈음한다.

- [x] **Step 1: 현재 deps 확인**

```bash
grep -A 20 "^dependencies = \[" pyproject.toml
```

Expected: `langchain>=1.2.17`, `langchain-google-genai>=4.2.2`, `langgraph>=1.1.10` 포함.

- [x] **Step 2: pyproject.toml 수정**

`langchain*` 3 항목 제거하고 `google-genai>=1.0` 추가:

```toml
dependencies = [
    # ... 기존 항목 유지
    "google-genai>=1.0",
    # langchain, langchain-google-genai, langgraph 제거
    # ...
]
```

- [x] **Step 3: uv sync 실행**

```bash
uv sync
```

Expected: lockfile 갱신, google-genai 설치 성공, langchain 제거됨.

- [x] **Step 4: 기존 테스트 GREEN 유지 확인**

```bash
uv run pytest -v 2>&1 | tail -5
```

Expected: 70 tests GREEN (Task 8 에서 main.py 깨짐을 fix 하기 전까지 langchain import 가 main.py 에만 있어 테스트는 영향 없음). 만약 깨지면 Task 8 을 먼저 수행하거나 main.py 의 langchain import 를 일시 주석.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): replace langchain* with google-genai (Phase 2 Task 1)"
```

---

### Task 2: CachePolicy frozen 모델

**Files:**
- Create: `best_agent_base/llm/cache_policy.py`
- Test: `tests/test_cache_policy.py`

매핑: FR-5 / D3 / AC-5

- [ ] **Step 1: failing test 작성**

```python
# tests/test_cache_policy.py
"""CachePolicy frozen 모델 검증 (FR-5, AC-5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.llm.cache_policy import CachePolicy


def test_default_policy_enabled():
    p = CachePolicy()
    assert p.enabled is True
    assert p.ttl_seconds == 3600
    assert p.force_invalidate is False


def test_disabled_policy():
    p = CachePolicy(enabled=False)
    assert p.enabled is False


def test_force_invalidate():
    p = CachePolicy(force_invalidate=True)
    assert p.force_invalidate is True


def test_custom_ttl():
    p = CachePolicy(ttl_seconds=60)
    assert p.ttl_seconds == 60


def test_frozen_immutable():
    p = CachePolicy()
    with pytest.raises(ValidationError):
        p.enabled = False  # type: ignore[misc]


def test_negative_ttl_rejected():
    with pytest.raises(ValidationError):
        CachePolicy(ttl_seconds=-1)
```

- [ ] **Step 2: 테스트 실행 확인 (RED)**

```bash
uv run pytest tests/test_cache_policy.py -v
```

Expected: FAIL — `ModuleNotFoundError: best_agent_base.llm.cache_policy`

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/llm/cache_policy.py
"""CachePolicy frozen 모델 — 도메인이 캐시 동작을 명시 컨트롤 (FR-5, D3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CachePolicy(BaseModel):
    """캐시 컨트롤 정책. 도메인이 generate() 호출 시 주입.

    - enabled: 캐시 사용 여부 (False 면 매 호출 신규)
    - ttl_seconds: Gemini CachedContent TTL (초)
    - force_invalidate: True 면 기존 캐시 무시하고 신규 생성
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    ttl_seconds: int = Field(default=3600, gt=0)
    force_invalidate: bool = False
```

- [ ] **Step 4: 테스트 GREEN 확인**

```bash
uv run pytest tests/test_cache_policy.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add best_agent_base/llm/cache_policy.py tests/test_cache_policy.py
git commit -m "feat(llm): add CachePolicy frozen model (Phase 2 Task 2)"
```

---

### Task 3: CacheMetrics + Event + Observer

**Files:**
- Create: `best_agent_base/llm/cache_metrics.py`
- Test: `tests/test_cache_metrics.py`

매핑: FR-6 / D5 / AC-6

- [ ] **Step 1: failing test 작성**

```python
# tests/test_cache_metrics.py
"""CacheMetrics + observer + event emit 검증 (FR-6, AC-6, D5)."""

from __future__ import annotations

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics


def test_event_values():
    assert CacheEvent.HIT.value == "hit"
    assert CacheEvent.MISS.value == "miss"
    assert CacheEvent.HASH_CHANGE.value == "hash_change"


def test_observer_receives_emit():
    received: list[tuple[CacheEvent, str]] = []
    metrics = CacheMetrics()
    metrics.add_observer(lambda ev, h: received.append((ev, h)))

    metrics.emit(CacheEvent.HIT, "abc123")
    metrics.emit(CacheEvent.MISS, "def456")

    assert received == [(CacheEvent.HIT, "abc123"), (CacheEvent.MISS, "def456")]


def test_stats_counter():
    metrics = CacheMetrics()
    metrics.emit(CacheEvent.HIT, "x")
    metrics.emit(CacheEvent.HIT, "x")
    metrics.emit(CacheEvent.MISS, "y")
    metrics.emit(CacheEvent.HASH_CHANGE, "y")

    stats = metrics.stats()
    assert stats["hit"] == 2
    assert stats["miss"] == 1
    assert stats["hash_change"] == 1


def test_multiple_observers_all_called():
    a: list[CacheEvent] = []
    b: list[CacheEvent] = []
    metrics = CacheMetrics()
    metrics.add_observer(lambda ev, h: a.append(ev))
    metrics.add_observer(lambda ev, h: b.append(ev))

    metrics.emit(CacheEvent.HIT, "k")
    assert a == [CacheEvent.HIT]
    assert b == [CacheEvent.HIT]


def test_no_observers_no_error():
    metrics = CacheMetrics()
    # observer 없어도 emit 정상 동작 + 카운터는 누적
    metrics.emit(CacheEvent.MISS, "k")
    assert metrics.stats()["miss"] == 1
```

- [ ] **Step 2: 테스트 RED 확인**

```bash
uv run pytest tests/test_cache_metrics.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/llm/cache_metrics.py
"""CacheMetrics + Event + Observer — 캐시 적중·미적중 슬롯 (FR-6, D5).

베이스는 인터페이스 + 카운터만. 실제 backend (Prometheus / OTel / 로깅) 는 도메인.
observer 는 동기 callable, fire-and-forget. 무거운 backend 는 도메인이 task 분리.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from enum import StrEnum


class CacheEvent(StrEnum):
    HIT = "hit"
    MISS = "miss"
    HASH_CHANGE = "hash_change"


CacheObserver = Callable[[CacheEvent, str], None]
"""(event, static_hash) → None. 동기 callable, 가볍게."""


class CacheMetrics:
    """Observer 등록 + 이벤트 emit + 누적 카운터."""

    def __init__(self) -> None:
        self._observers: list[CacheObserver] = []
        self._counter: Counter[str] = Counter()

    def add_observer(self, observer: CacheObserver) -> None:
        self._observers.append(observer)

    def emit(self, event: CacheEvent, static_hash: str) -> None:
        self._counter[event.value] += 1
        for obs in self._observers:
            obs(event, static_hash)

    def stats(self) -> dict[str, int]:
        return dict(self._counter)
```

- [ ] **Step 4: 테스트 GREEN 확인**

```bash
uv run pytest tests/test_cache_metrics.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add best_agent_base/llm/cache_metrics.py tests/test_cache_metrics.py
git commit -m "feat(llm): add CacheMetrics + Event + Observer (Phase 2 Task 3)"
```

---

### Task 4: LLMClient Protocol + LLMResponse + TokenUsage

**Files:**
- Create: `best_agent_base/llm/client.py`
- Test: `tests/test_llm_client_protocol.py`

매핑: FR-1 / D2 / AC-1, AC-2 (AC-2 의 GeminiClient 적합성은 Task 6 에서)

- [ ] **Step 1: failing test 작성**

```python
# tests/test_llm_client_protocol.py
"""LLMClient Protocol runtime_checkable 검증 (FR-1, AC-1)."""

from __future__ import annotations

from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient, LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


def test_token_usage_frozen():
    u = TokenUsage(input_tokens=10, output_tokens=5)
    assert u.cached_tokens == 0
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        u.input_tokens = 99  # type: ignore[misc]


def test_llm_response_fields():
    r = LLMResponse(
        text="hi",
        static_hash="abc",
        cache_hit=False,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    assert r.text == "hi"
    assert r.static_hash == "abc"
    assert r.cache_hit is False
    assert r.usage.input_tokens == 10


def test_protocol_runtime_checkable_compliant():
    class Compliant:
        async def generate(
            self, ctx: RenderContext, *, cache_policy: CachePolicy | None = None
        ) -> LLMResponse:
            return LLMResponse(
                text="x",
                static_hash="x",
                cache_hit=False,
                usage=TokenUsage(input_tokens=0, output_tokens=0),
            )

        def count_tokens(self, text: str) -> int:
            return len(text)

    assert isinstance(Compliant(), LLMClient)


def test_protocol_runtime_checkable_noncompliant():
    class Noncompliant:
        # generate / count_tokens 둘 다 없음
        pass

    assert not isinstance(Noncompliant(), LLMClient)
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_llm_client_protocol.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/llm/client.py
"""LLMClient Protocol + LLMResponse + TokenUsage (FR-1, D2 B-thin).

얇은 Protocol — generate (async) + count_tokens (슬롯) 두 메서드만.
스트리밍·도구 바인딩·에러 envelope 는 후속 Phase. (PRD §5 OOS-3..6)
"""

from __future__ import annotations

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
    """Provider-agnostic LLM 호출 슬롯 (B-thin)."""

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse: ...

    def count_tokens(self, text: str) -> int: ...
```

- [ ] **Step 4: GREEN 확인**

```bash
uv run pytest tests/test_llm_client_protocol.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add best_agent_base/llm/client.py tests/test_llm_client_protocol.py
git commit -m "feat(llm): add LLMClient Protocol + LLMResponse + TokenUsage (Phase 2 Task 4)"
```

---

### Task 5: build_gemini_messages

**Files:**
- Create: `best_agent_base/llm/messages.py`
- Test: `tests/test_llm_messages.py`

매핑: FR-3 / AC-3

- [ ] **Step 1: failing test 작성**

```python
# tests/test_llm_messages.py
"""build_gemini_messages — Phase 1 render(ctx) 출력 → (static, dynamic) split (FR-3, AC-3)."""

from __future__ import annotations

from best_agent_base.llm.messages import build_gemini_messages
from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.render import RenderContext


def test_split_at_boundary():
    static, dynamic = build_gemini_messages(RenderContext())
    # 베이스에는 동적부 없음 → dynamic 은 빈 문자열
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY not in static
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY not in dynamic
    assert dynamic == ""
    assert len(static) > 0  # 베이스 7섹션은 항상 있음


def test_static_matches_render_static_part():
    """build_gemini_messages 의 static = render(ctx) 의 BOUNDARY 앞 부분."""
    from best_agent_base.prompts.render import render

    rendered = render(RenderContext())
    static, dynamic = build_gemini_messages(RenderContext())
    expected_static, _, expected_dynamic = rendered.partition(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    assert static == expected_static.rstrip("\n")
    assert dynamic == expected_dynamic.lstrip("\n")
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_llm_messages.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/llm/messages.py
"""Phase 1 render(ctx) → Gemini provider 메시지 구조 변환 (FR-3).

BOUNDARY 마커 기준 (static, dynamic) 으로 정확히 split. 정적부 = 캐시 대상.
"""

from __future__ import annotations

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.render import RenderContext, render


def build_gemini_messages(ctx: RenderContext) -> tuple[str, str]:
    """Returns (static_text, dynamic_text), split at SYSTEM_PROMPT_DYNAMIC_BOUNDARY.

    Phase 1 `render(ctx)` 출력은 "<static>\n\n<BOUNDARY>\n\n<dynamic>" 형식.
    정확히 BOUNDARY 마커에서 분리해 trailing/leading whitespace 만 정리.
    """
    rendered = render(ctx)
    static_part, _, dynamic_part = rendered.partition(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    return static_part.rstrip("\n"), dynamic_part.lstrip("\n")
```

- [ ] **Step 4: GREEN 확인**

```bash
uv run pytest tests/test_llm_messages.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add best_agent_base/llm/messages.py tests/test_llm_messages.py
git commit -m "feat(llm): add build_gemini_messages (Phase 2 Task 5)"
```

---

### Task 6: GeminiClient 재작성 (CachedContent + race lock)

**Files:**
- Modify: `best_agent_base/llm/gemini.py` (LangChain 제거 + GeminiClient 신규)
- Test: `tests/test_gemini_adapter.py`, `tests/test_cache_key_stability.py`

매핑: FR-2, FR-4 / D1, D6 / R-1, R-2 / AC-2, AC-4, AC-7

이 task 는 가장 큼 — TDD step 을 5에서 7 로 확장 (cache hit / cache miss / race lock 각각 검증).

- [ ] **Step 1: failing tests 작성 (gemini adapter)**

```python
# tests/test_gemini_adapter.py
"""GeminiClient 재작성 검증 (FR-2, FR-4, D1, D6 / AC-2, AC-4)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.llm.profiles import DEFAULT_CHAT
from best_agent_base.prompts.render import RenderContext


def _make_client(monkeypatch: pytest.MonkeyPatch) -> tuple[GeminiClient, MagicMock]:
    """Fake google-genai SDK client 주입. caches.create / models.generate_content_async 호출 추적."""
    fake_sdk = MagicMock()
    fake_sdk.aio.caches.create = AsyncMock(
        return_value=MagicMock(name="cached_content_obj", name_attr="cachedContents/abc")
    )
    fake_sdk.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(
            text="hi",
            usage_metadata=MagicMock(
                prompt_token_count=10, candidates_token_count=5, cached_content_token_count=0
            ),
        )
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr(
        "best_agent_base.llm.gemini._build_genai_client", lambda: fake_sdk
    )
    client = GeminiClient(profile=DEFAULT_CHAT)
    return client, fake_sdk


def test_protocol_compliance(monkeypatch: pytest.MonkeyPatch):
    client, _ = _make_client(monkeypatch)
    assert isinstance(client, LLMClient)


@pytest.mark.asyncio
async def test_first_call_creates_cache_emits_miss(monkeypatch: pytest.MonkeyPatch):
    client, fake = _make_client(monkeypatch)
    metrics = CacheMetrics()
    client._metrics = metrics
    events: list[CacheEvent] = []
    metrics.add_observer(lambda ev, h: events.append(ev))

    resp = await client.generate(RenderContext())

    assert resp.cache_hit is False
    assert resp.text == "hi"
    assert CacheEvent.MISS in events
    fake.aio.caches.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_call_reuses_cache_emits_hit(monkeypatch: pytest.MonkeyPatch):
    client, fake = _make_client(monkeypatch)
    metrics = CacheMetrics()
    client._metrics = metrics
    events: list[CacheEvent] = []
    metrics.add_observer(lambda ev, h: events.append(ev))

    await client.generate(RenderContext())
    fake.aio.caches.create.reset_mock()
    resp2 = await client.generate(RenderContext())

    assert resp2.cache_hit is True
    fake.aio.caches.create.assert_not_awaited()  # 두 번째 호출은 cache 재사용
    assert events.count(CacheEvent.HIT) == 1


@pytest.mark.asyncio
async def test_disabled_policy_skips_cache(monkeypatch: pytest.MonkeyPatch):
    client, fake = _make_client(monkeypatch)
    await client.generate(RenderContext(), cache_policy=CachePolicy(enabled=False))
    fake.aio.caches.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_force_invalidate_creates_new_cache(monkeypatch: pytest.MonkeyPatch):
    client, fake = _make_client(monkeypatch)
    await client.generate(RenderContext())
    fake.aio.caches.create.reset_mock()
    await client.generate(RenderContext(), cache_policy=CachePolicy(force_invalidate=True))
    fake.aio.caches.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_calls_create_cache_once(monkeypatch: pytest.MonkeyPatch):
    """R-1 race: 동시 호출에서 동일 hash 의 CachedContent 가 단 한 번만 생성됨 (asyncio.Lock)."""
    client, fake = _make_client(monkeypatch)

    async def slow_create(*args, **kwargs):
        await asyncio.sleep(0.05)
        return MagicMock(name_attr="cachedContents/abc")

    fake.aio.caches.create = AsyncMock(side_effect=slow_create)

    await asyncio.gather(*[client.generate(RenderContext()) for _ in range(5)])

    assert fake.aio.caches.create.await_count == 1


def test_count_tokens_slot_returns_int(monkeypatch: pytest.MonkeyPatch):
    """count_tokens 는 슬롯만 — Phase 9 본격 구현 전엔 conservative 추정으로 충분."""
    client, _ = _make_client(monkeypatch)
    n = client.count_tokens("hello world")
    assert isinstance(n, int)
    assert n >= 0
```

- [ ] **Step 2: failing test 작성 (cache key stability)**

```python
# tests/test_cache_key_stability.py
"""캐시 키 결정성 검증 (NFR-3, AC-7) — 동일 ctx → 동일 key, N=10 안정."""

from __future__ import annotations

from best_agent_base.llm.gemini import _cache_key_for
from best_agent_base.prompts.render import RenderContext


def test_same_ctx_same_key_n10():
    ctx = RenderContext()
    keys = {_cache_key_for(ctx) for _ in range(10)}
    assert len(keys) == 1
```

- [ ] **Step 3: RED 확인**

```bash
uv run pytest tests/test_gemini_adapter.py tests/test_cache_key_stability.py -v
```

Expected: FAIL (LangChain 기반 옛 gemini.py 라 새 GeminiClient 클래스 없음).

- [ ] **Step 4: gemini.py 재작성 (LangChain 제거 + GeminiClient + cache lock)**

```python
# best_agent_base/llm/gemini.py
"""Gemini 어댑터 — google-genai 직접, CachedContent 통합 (FR-2, FR-4, D1).

LangChain 제거 (D1 결정). 인스턴스 단위 in-memory cache map (D4).
asyncio.Lock per static_hash 로 R-1 race 완화. SDK 예외는 그대로 전파 (D6),
단 cache 생성 실패는 캐시 우회 + miss event 후 일반 호출 fallback.
"""

from __future__ import annotations

import asyncio
import os

from google import genai
from google.genai import types

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.llm.messages import build_gemini_messages
from best_agent_base.llm.profiles import DEFAULT_CHAT, ModelProfile
from best_agent_base.prompts.render import RenderContext, get_static_hash


def _build_genai_client() -> genai.Client:
    """google-genai SDK Client 인스턴스. 테스트에서 monkeypatch 가능."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY 또는 GEMINI_API_KEY 환경 변수가 설정되어 있지 않습니다.")
    return genai.Client(api_key=api_key)


def _cache_key_for(ctx: RenderContext) -> str:
    """캐시 키 = Phase 1 의 정적 해시. 결정성 보장 (NFR-3)."""
    return get_static_hash(ctx)


class GeminiClient:
    """LLMClient 적합 Gemini 참조 구현. 인스턴스 단위 in-memory cache map (D4)."""

    def __init__(
        self,
        profile: ModelProfile = DEFAULT_CHAT,
        *,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self._profile = profile
        self._metrics = metrics if metrics is not None else CacheMetrics()
        self._sdk = _build_genai_client()
        self._cache_map: dict[str, str] = {}  # static_hash → cachedContents/<id>
        self._locks: dict[str, asyncio.Lock] = {}  # per-hash race lock (R-1)
        self._last_hash: str | None = None  # HASH_CHANGE 감지용

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def _get_or_create_cached_content(
        self, key: str, static_text: str, ttl_seconds: int
    ) -> str | None:
        """캐시 조회·생성. 실패 시 None 반환 → 호출자가 캐시 우회 fallback (D6)."""
        async with self._lock_for(key):
            existing = self._cache_map.get(key)
            if existing is not None:
                return existing
            try:
                cached = await self._sdk.aio.caches.create(
                    model=self._profile.model.value,
                    config=types.CreateCachedContentConfig(
                        system_instruction=static_text,
                        ttl=f"{ttl_seconds}s",
                    ),
                )
            except Exception:
                # 캐시 생성 실패는 호출 자체를 막지 않음 (D6 fallback)
                return None
            cache_name = getattr(cached, "name_attr", None) or getattr(cached, "name", None)
            if cache_name is not None:
                self._cache_map[key] = cache_name
            return cache_name

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = build_gemini_messages(ctx)
        key = _cache_key_for(ctx)

        # HASH_CHANGE 감지 (R-4 가시성)
        if self._last_hash is not None and self._last_hash != key:
            self._metrics.emit(CacheEvent.HASH_CHANGE, key)
        self._last_hash = key

        cached_name: str | None = None
        cache_hit = False

        if policy.enabled and not policy.force_invalidate:
            cached_name = self._cache_map.get(key)
            if cached_name is not None:
                cache_hit = True
                self._metrics.emit(CacheEvent.HIT, key)
        if policy.enabled and (cached_name is None or policy.force_invalidate):
            if policy.force_invalidate:
                self._cache_map.pop(key, None)
            cached_name = await self._get_or_create_cached_content(
                key, static_text, policy.ttl_seconds
            )
            self._metrics.emit(CacheEvent.MISS, key)

        # SDK 호출 — cached_content 가 있으면 system_instruction 우회, 없으면 직접 주입
        config = (
            types.GenerateContentConfig(cached_content=cached_name)
            if cached_name is not None
            else types.GenerateContentConfig(system_instruction=static_text)
        )
        result = await self._sdk.aio.models.generate_content(
            model=self._profile.model.value,
            contents=dynamic_text or " ",
            config=config,
        )

        usage = self._extract_usage(result)
        return LLMResponse(
            text=getattr(result, "text", ""),
            static_hash=key,
            cache_hit=cache_hit,
            usage=usage,
        )

    @staticmethod
    def _extract_usage(result: object) -> TokenUsage:
        meta = getattr(result, "usage_metadata", None)
        if meta is None:
            return TokenUsage(input_tokens=0, output_tokens=0)
        return TokenUsage(
            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
            cached_tokens=getattr(meta, "cached_content_token_count", 0) or 0,
        )

    def count_tokens(self, text: str) -> int:
        # Phase 9 본격 — 현재는 conservative 추정 (단어 1.3토큰 가정)
        return int(len(text.split()) * 1.3)
```

- [ ] **Step 5: GREEN 확인**

```bash
uv run pytest tests/test_gemini_adapter.py tests/test_cache_key_stability.py -v
```

Expected: 8 PASS (gemini_adapter 7 + cache_key_stability 1).

- [ ] **Step 6: 전체 테스트 GREEN 확인 + ruff**

```bash
uv run pytest -v 2>&1 | tail -10 && uv run ruff check .
```

Expected: 모든 테스트 GREEN, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add best_agent_base/llm/gemini.py tests/test_gemini_adapter.py tests/test_cache_key_stability.py
git commit -m "feat(llm): rewrite gemini.py with google-genai + CachedContent + race lock (Phase 2 Task 6)"
```

---

### Task 7: NFR invariant 확장 (test_init_purity + test_no_domain_vocab)

**Files:**
- Modify: `tests/test_init_purity.py` — `best_agent_base/llm/__init__.py` 검증 추가
- Modify: `tests/test_no_domain_vocab.py` — `best_agent_base/llm/` 트리 추가

매핑: NFR-1, NFR-2 / AC-8, AC-9

- [ ] **Step 1: 현재 테스트 파일 확인**

```bash
cat tests/test_init_purity.py tests/test_no_domain_vocab.py
```

Expected: Phase 1 패턴 — `prompts/__init__.py` 만 검증.

- [ ] **Step 2: test_init_purity.py 확장 (LLM `__init__` 추가)**

기존 검증 대상 리스트에 `best_agent_base/llm/__init__.py` 추가. AST 로 docstring-only 인지 검사.

```python
# tests/test_init_purity.py 의 검증 대상 리스트에 추가
TARGETS = [
    "best_agent_base/__init__.py",
    "best_agent_base/prompts/__init__.py",
    "best_agent_base/llm/__init__.py",  # Phase 2 추가
]
```

(정확한 변경 위치는 기존 파일 구조에 따라 — 리스트가 있으면 항목 추가, 없으면 동일 검증을 별도 함수로 추가.)

- [ ] **Step 3: test_no_domain_vocab.py 확장 (LLM 트리 추가)**

기존 grep 대상 트리 리스트에 `best_agent_base/llm/` 추가:

```python
# tests/test_no_domain_vocab.py 의 grep 대상에 추가
SCAN_DIRS = [
    Path("best_agent_base/prompts"),
    Path("best_agent_base/llm"),  # Phase 2 추가
]
```

(정확한 변경 위치는 기존 파일 구조에 따라 조정.)

- [ ] **Step 4: 두 테스트 GREEN 확인**

```bash
uv run pytest tests/test_init_purity.py tests/test_no_domain_vocab.py -v
```

Expected: PASS. 만약 RED 면 forbidden 어휘를 src 에서 제거해야 함 (Task 2~6 작성 시 NFR-1 일관 적용했으면 통과).

- [ ] **Step 5: Commit**

```bash
git add tests/test_init_purity.py tests/test_no_domain_vocab.py
git commit -m "test(llm): extend NFR-1/NFR-2 invariants to llm tree (Phase 2 Task 7)"
```

---

### Task 8: R-3 main.py 마이그레이션

**Files:**
- Modify: `main.py` (langgraph + langchain 제거, GeminiClient 사용)

매핑: R-3 / 그루밍 노트 #2 동시 처리

선택 (a) 추천: `main.py` 를 `GeminiClient` 기반 단일 호출 데모로 재작성. langgraph 데모는 별도 프로젝트 영역이라 베이스에 둘 이유 없음.

- [ ] **Step 1: 현재 main.py 확인** (이미 위에서 읽음 — 8행 `langgraph` import + 14행 `get_gemini()` 호출)

- [ ] **Step 2: main.py 재작성**

```python
# main.py
"""best_agent_base 단순 호출 데모.

Phase 2 GeminiClient 사용. 도메인 프로젝트는 이 패턴을 참고.
"""

from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def _main() -> None:
    load_dotenv()
    client = GeminiClient()
    resp = await client.generate(RenderContext())
    print(resp.text)
    print(f"\n[cache_hit={resp.cache_hit} static_hash={resp.static_hash}]")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: import / lint 확인**

```bash
uv run ruff check main.py
```

Expected: clean.

- [ ] **Step 4: 전체 테스트 GREEN 확인**

```bash
uv run pytest -v 2>&1 | tail -5
```

Expected: 모든 테스트 GREEN. main.py 는 테스트가 없지만 (data ingestion 데모) langchain import 가 사라져 import 깨짐 없음.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "refactor(main): migrate from langgraph/langchain to GeminiClient (Phase 2 Task 8)"
```

---

### Task 9: 통합 테스트 + 최종 GREEN/clean 검증

**Files:**
- Modify: `tests/conftest.py` — autouse `cache_metrics_isolation` fixture 도입 (선택, 그루밍 노트 #3 부분 처리)
- 최종 확인: `uv run pytest -v && uv run ruff check . && uv run ruff format --check .`

매핑: AC-10 (전체 GREEN + ruff clean)

- [ ] **Step 1: conftest.py 신규 또는 확장**

만약 `tests/conftest.py` 부재면 신규 생성. autouse fixture 로 GeminiClient 인스턴스 부작용 격리:

```python
# tests/conftest.py
"""Pytest 공통 fixtures — registry / metrics 격리 (Phase 1+2 패턴)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.registry import registry


@pytest.fixture(autouse=True)
def restore_registry():
    """Phase 1 SectionRegistry snapshot/restore — 4 테스트 파일 중복 DRY."""
    snapshot = dict(registry._sections)  # noqa: SLF001 — test fixture 한정
    try:
        yield
    finally:
        registry._sections.clear()  # noqa: SLF001
        registry._sections.update(snapshot)  # noqa: SLF001
```

(GeminiClient 는 인스턴스 단위 cache_map 이라 별도 격리 불필요 — 각 테스트에서 새 인스턴스.)

- [ ] **Step 2: 기존 4 테스트 파일에서 중복 snapshot/restore 제거** (권장 — 시간 부족 시 Phase 3 진입 시 처리)

`test_prompts_*.py` 4 파일에 박혀있던 snapshot/restore 패턴이 conftest autouse 와 중복. 이중 snapshot/restore 자체는 안전하지만 fixture 의도가 흐려지므로 단순화 권장 (4 파일에서 함수-내 snapshot 코드 삭제). autouse 와 충돌 시나리오 점검 — 함수-내 snapshot 이 autouse fixture 의 yield 후 cleanup 보다 먼저 실행되는지 (정상 케이스: 함수-내 try/finally 가 inner, autouse 가 outer 라 양쪽 다 동작). 충돌 없으면 4 파일 정리 후 commit. 시간 부족하면 본 Phase 진입 시점에 그루밍 노트로 이월.

- [ ] **Step 3: 전체 GREEN + ruff + format 검증**

```bash
uv run pytest -v 2>&1 | tail -10 && uv run ruff check . && uv run ruff format --check .
```

Expected: 모든 테스트 GREEN (Phase 1 70 + Phase 2 신규 24~ ≈ 94 tests), ruff check clean, format clean.

- [ ] **Step 4: AC 전수 체크**

| AC | 검증 |
|---|---|
| AC-1 | test_llm_client_protocol.py::test_protocol_runtime_checkable_* GREEN |
| AC-2 | test_gemini_adapter.py::test_protocol_compliance GREEN |
| AC-3 | test_llm_messages.py::test_split_at_boundary, test_static_matches_render_static_part GREEN |
| AC-4 | test_gemini_adapter.py::test_first_call_creates_cache_emits_miss + test_second_call_reuses_cache_emits_hit GREEN |
| AC-5 | test_cache_policy.py 6 cases GREEN, test_gemini_adapter.py::test_disabled_policy_skips_cache + test_force_invalidate_creates_new_cache GREEN |
| AC-6 | test_cache_metrics.py 5 cases GREEN |
| AC-7 | test_cache_key_stability.py::test_same_ctx_same_key_n10 GREEN |
| AC-8 | test_init_purity.py 확장본 GREEN |
| AC-9 | test_no_domain_vocab.py 확장본 GREEN |
| AC-10 | 전체 GREEN + ruff clean |

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py
git commit -m "test(llm): add autouse registry isolation fixture + Phase 2 final GREEN (Phase 2 Task 9)"
```

---

## 2. 위험 코드 지점

tech-design §6 R-1..6 매핑 — 각 위험을 구현 시 코드 한 줄 한 줄에 어떻게 박는지:

- `best_agent_base/llm/gemini.py:GeminiClient._get_or_create_cached_content` (Task 6) — **race**: 동시 호출 시 동일 hash 의 `CachedContent` 중복 생성 (R-1). **mitigation**: `asyncio.Lock` per `static_hash` (`_locks` dict + `_lock_for(key)`). test_gemini_adapter.py::test_concurrent_calls_create_cache_once 로 검증.
- `best_agent_base/llm/gemini.py:GeminiClient._get_or_create_cached_content` (Task 6) — **side-effect**: 캐시 생성 실패 (네트워크 / 인증 / TTL 거부 등) 가 호출 자체를 막을 위험 (R-2 의 perf 우려와 다른 fallback 경로, D6 와 연동). **mitigation**: `try/except Exception` 후 `None` 반환 → 호출자가 캐시 우회 + miss event 후 일반 호출 fallback. SDK 예외는 본 cache 경로에서만 흡수, 일반 generate 호출 경로는 D6 대로 그대로 전파.
- `best_agent_base/llm/gemini.py:GeminiClient.generate` cache miss 분기 (Task 6) — **perf**: cache miss 첫 호출이 (a) `caches.create()` + (b) `generate_content()` 두 RTT 일 수 있음 (R-2). **mitigation**: 의도된 trade-off, 두 번째 호출부터 적중 (test_second_call_reuses_cache_emits_hit 로 검증). 1회 비용은 도메인이 cache pre-warm 으로 제거 가능.
- `pyproject.toml` deps + `main.py` (Task 1, Task 8) — **breaking**: `langchain*` 제거 + `get_gemini()` 반환 타입 변경으로 `main.py` 의 `langgraph` 데모 깨짐 (R-3). **mitigation**: Task 8 에서 main.py 를 `GeminiClient` 사용으로 재작성. 기존 `get_gemini()` 함수는 Task 6 의 재작성 시 동시 제거.
- `best_agent_base/llm/gemini.py:GeminiClient.generate` HASH_CHANGE emit (Task 6) — **side-effect**: `static` 섹션에 마커 누적 시 hash 변동 → 캐시 자동 무효화 (R-4). **mitigation**: 의도된 동작, `CacheEvent.HASH_CHANGE` emit 으로 도메인 가시성 제공. test_cache_metrics.py::test_stats_counter 가 HASH_CHANGE 이벤트 카운트를 검증.
- `best_agent_base/llm/cache_metrics.py:CacheMetrics.emit` (Task 3) — **perf**: oversized observer 가 동기 callable 이라 호출 path 지연 가능 (R-5). **mitigation**: 베이스 정책 명문화 — observer 는 가벼워야 함. 도메인 인터페이스 가이드 (`docs/interfaces/phase-2-llm-client.md`) 의 §확장 포인트 + 금지 사항에 명시. 무거운 backend 는 도메인이 자기 안에서 task 분리.
- `best_agent_base/llm/cache_policy.py:CachePolicy` (Task 2) — **breaking**: 향후 필드 추가 시 frozen 모델 호환성 (R-6). **mitigation**: Pydantic `Field(default=...)` 로 모든 신규 필드는 default 보장. 도메인이 자기 정책 클래스 만들고 싶으면 별도 BaseModel + 변환 함수 (베이스가 강제 안 함).

## 3. 롤백 전략

- **Code**: Phase 2 의 9 task 는 각 task 끝에 1개 commit (총 9개). 문제 발생 시 `git revert <SHA>` 또는 `git reset --hard <pre-phase-2-SHA>` (현재 main HEAD = `1a0231e` 직후의 새 commit 들). Phase 1 산출물 영향 없음 (prompts/ 트리 read-only 참조만).
- **Deps**: `pyproject.toml` 변경 (Task 1) 만 되돌리면 langchain 환경 복원. `git revert <Task1-SHA> && uv sync` 로 즉시.
- **DB**: 변경 없음 (D4 in-memory only) — 롤백 대상 없음.
- **Config / 환경 변수**: `GOOGLE_API_KEY` / `GEMINI_API_KEY` 는 기존 그대로 사용 (Task 0 / Phase 0 과 동일) — 추가 환경 변수 없음.
- **외부 시스템**: Gemini API 의 `CachedContent` 가 TTL 후 자동 만료. 명시 삭제 필요 없음 (베이스에 cleanup 코드 안 둠 — 도메인이 필요시 자기 cleanup).

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 19:48] [구현계획서-수정]
- **id**: CH-20260503-003
- **이유**: 신규 구현계획서 (writing-plans). PRD CH-001 + tech-design CH-002 의 FR-1..6 / NFR-1..4 / D1..D6 / R-1..6 / AC-1..10 을 9 task TDD cycle 로 분해. verifying-spec 보고서 권장 3번 (Task 9 Step 2 의 conftest 중복 제거 명확화) 반영.
- **무엇이**: phase-2-llm-client-implementation-plan.md 전체 (§1 Task 1..9 + §2 위험 코드 지점 7건 + §3 롤백 전략) + Task 9 Step 2 명확화
- **영향범위**: 없음 (최초 생성). 후속 영향 = `/execute-plan` 실행 시 9 task 순차 commit (Task 1 deps → Task 2 CachePolicy → Task 3 CacheMetrics → Task 4 LLMClient → Task 5 messages → Task 6 GeminiClient + race lock → Task 7 NFR invariant 확장 → Task 8 main.py 마이그레이션 → Task 9 conftest + 최종 GREEN). 외부 영향 = `pyproject.toml` deps 교체 (`langchain*` → `google-genai`), `main.py` 재작성 (langgraph demo 제거).
- **연관 항목**: CH-20260503-001 (PRD), CH-20260503-002 (tech-design)

### [2026-05-03 19:52] [코드-수정] (task: Task 1 — deps 교체)
- **id**: CH-20260503-004
- **이유**: D1 결정 (langchain 추상화 제거 + google-genai 직접 사용 — Gemini `CachedContent` API 가 google-genai 의 1급 기능이고 LangChain 우회 시 본 Phase 핵심 KV 캐싱 컨트롤과 정합 불가) 의 첫 실행 단계. 코드 변경 전 의존성부터 정리하여 Task 4..6 (LLMClient Protocol, build_gemini_messages, GeminiClient 재작성) 가 google-genai SDK 위에서 구현 가능하게 한다.
- **무엇이**: pyproject.toml, uv.lock
- **영향범위**: `pyproject.toml` dependencies 블록 (langchain/langchain-google-genai/langgraph 3 항목 제거 → google-genai>=1.0 1 항목 추가). `uv.lock` 자동 재생성 — langchain 계열 transitive deps 제거, google-genai 및 그 deps 추가. `main.py` 는 langchain/langgraph import 가 있지만 module import 만 하고 실제 실행은 `if __name__ == "__main__"` 가드 안이라 pytest 70 GREEN 영향 없음 (Task 8 에서 main.py 마이그레이션 시 처리). 후속 영향 = Task 4..6 의 google-genai SDK 사용 가능, Task 8 의 main.py 재작성 강제.
- **위험 카테고리**: breaking
- **세부 변경 (2건)**:
  - `pyproject.toml:dependencies` — langchain>=1.2.17 / langchain-google-genai>=4.2.2 / langgraph>=1.1.10 제거, google-genai>=1.0 추가
  - `uv.lock` — `uv sync` 자동 갱신 (langchain 계열 transitive deps 제거, google-genai==1.74.0 + 그 transitive deps 추가)
- **변경 전 코드** (per file)
  ```toml
  // file: pyproject.toml (변경된 dependencies 블록만)
  dependencies = [
      "alembic>=1.18.4",
      "asyncpg>=0.31.0",
      "fastapi>=0.136.1",
      "langchain>=1.2.17",
      "langchain-google-genai>=4.2.2",
      "langgraph>=1.1.10",
      "pydantic-settings>=2.14.0",
      "python-dotenv>=1.2.2",
      "sqlalchemy[asyncio]>=2.0.49",
      "tiktoken>=0.12.0",
      "uvicorn>=0.46.0",
  ]
  ```
- **변경 후 코드** (per file)
  ```toml
  // file: pyproject.toml (변경된 dependencies 블록만)
  dependencies = [
      "alembic>=1.18.4",
      "asyncpg>=0.31.0",
      "fastapi>=0.136.1",
      "google-genai>=1.0",
      "pydantic-settings>=2.14.0",
      "python-dotenv>=1.2.2",
      "sqlalchemy[asyncio]>=2.0.49",
      "tiktoken>=0.12.0",
      "uvicorn>=0.46.0",
  ]
  ```
- **검증**: `uv sync` 성공 (google-genai==1.74.0 설치 확인, langchain/langgraph 제거 확인). `uv run pytest -v` → 70 passed (기존 테스트 GREEN 유지).
- **연관 항목**: CH-20260503-003 (구현계획서 — Task 1 정의)

### [2026-05-03 20:05] [코드-수정] (task: Task 2 — CachePolicy frozen 모델)
- **id**: CH-20260503-005
- **이유**: D3 결정 (3-필드 CachePolicy frozen 모델 — enabled/ttl_seconds/force_invalidate) 의 구현. FR-5 (도메인이 캐시 동작 명시 컨트롤) / AC-5 (CachePolicy 의 enabled=False / force_invalidate=True 동작이 GeminiClient 와 정합) 충족. Task 6 의 `generate(cache_policy=None)` 시 None → CachePolicy() 디폴트 fallback 의 baseline. R-6 (frozen 모델 향후 필드 추가 호환성) 은 모든 신규 필드 default 보장 + None fallback 으로 mitigate.
- **무엇이**: best_agent_base/llm/cache_policy.py (신규), tests/test_cache_policy.py (신규 — 6 cases)
- **영향범위**: `best_agent_base/llm/cache_policy.py` 신규 모듈 (15 LOC) — Pydantic BaseModel + ConfigDict(frozen=True) + Field(default=3600, gt=0). public API = `CachePolicy` symbol 1개. `tests/test_cache_policy.py` 신규 (32 LOC, 6 tests). 기존 70 테스트 무영향. 후속 영향 = Task 4 의 LLMClient.generate 시그니처가 `cache_policy: CachePolicy | None = None` 으로 본 모델 import, Task 6 의 GeminiClient 가 enabled/force_invalidate 분기 + ttl_seconds 를 caches.create 에 전달.
- **위험 카테고리**: breaking — 신규 public API (`best_agent_base.llm.cache_policy.CachePolicy`)
- **세부 변경 (2건)**:
  - `best_agent_base/llm/cache_policy.py` — 신규 (frozen Pydantic BaseModel: `enabled: bool = True`, `ttl_seconds: int = Field(default=3600, gt=0)`, `force_invalidate: bool = False`)
  - `tests/test_cache_policy.py` — 신규 6 cases (default/disabled/force_invalidate/custom_ttl/frozen_immutable/negative_ttl_rejected)
- **변경 전 코드**: 없음 — 신규 모듈
- **변경 후 코드** (per file)
  ```python
  # file: best_agent_base/llm/cache_policy.py
  """CachePolicy frozen 모델 — 도메인이 캐시 동작을 명시 컨트롤 (FR-5, D3)."""

  from __future__ import annotations

  from pydantic import BaseModel, ConfigDict, Field


  class CachePolicy(BaseModel):
      """캐시 컨트롤 정책. 도메인이 generate() 호출 시 주입.

      - enabled: 캐시 사용 여부 (False 면 매 호출 신규)
      - ttl_seconds: Gemini CachedContent TTL (초)
      - force_invalidate: True 면 기존 캐시 무시하고 신규 생성
      """

      model_config = ConfigDict(frozen=True)

      enabled: bool = True
      ttl_seconds: int = Field(default=3600, gt=0)
      force_invalidate: bool = False
  ```
  ```python
  # file: tests/test_cache_policy.py
  """CachePolicy frozen 모델 검증 (FR-5, AC-5)."""

  from __future__ import annotations

  import pytest
  from pydantic import ValidationError

  from best_agent_base.llm.cache_policy import CachePolicy


  def test_default_policy_enabled():
      p = CachePolicy()
      assert p.enabled is True
      assert p.ttl_seconds == 3600
      assert p.force_invalidate is False


  def test_disabled_policy():
      p = CachePolicy(enabled=False)
      assert p.enabled is False


  def test_force_invalidate():
      p = CachePolicy(force_invalidate=True)
      assert p.force_invalidate is True


  def test_custom_ttl():
      p = CachePolicy(ttl_seconds=60)
      assert p.ttl_seconds == 60


  def test_frozen_immutable():
      p = CachePolicy()
      with pytest.raises(ValidationError):
          p.enabled = False  # type: ignore[misc]


  def test_negative_ttl_rejected():
      with pytest.raises(ValidationError):
          CachePolicy(ttl_seconds=-1)
  ```
- **검증**: `uv run pytest tests/test_cache_policy.py -v` → 6 passed (RED→GREEN 사이클 완료).
- **연관 항목**: CH-20260503-003 (구현계획서 — Task 2 정의), CH-20260503-004 (Task 1 deps 교체 — google-genai 환경 위에서 본 모델 동작)

### [2026-05-03 20:18] [코드-수정] (task: Task 3 — CacheMetrics + Event + Observer)
- **id**: CH-20260503-006
- **이유**: D5 결정 (동기 observer `Callable[[CacheEvent, str], None]` — 비동기/queue 대안은 베이스 단순성 위배로 기각) 의 구현. FR-6 (캐시 적중·미적중 메트릭 슬롯) / AC-6 (CacheMetrics 가 hit/miss/hash_change 3 이벤트와 observer 등록을 노출) 충족. 베이스는 인터페이스 + 누적 카운터만 제공하고, 실제 backend (Prometheus / OTel / 로깅) 는 도메인이 observer 로 주입한다. R-5 (oversized observer 가 generate() 호출 path 를 지연시킬 위험) 는 인터페이스 가이드 + 본 모듈 docstring 으로 "observer 는 가벼워야 함, 무거우면 도메인이 task 분리" 정책을 명시하여 mitigate.
- **무엇이**: best_agent_base/llm/cache_metrics.py (신규), tests/test_cache_metrics.py (신규 — 5 cases)
- **영향범위**: `best_agent_base/llm/cache_metrics.py` 신규 모듈 (~30 LOC) — `CacheEvent` StrEnum (HIT/MISS/HASH_CHANGE), `CacheObserver` 타입 alias, `CacheMetrics` 클래스 (add_observer/emit/stats). public API = 3 symbol 추가. `tests/test_cache_metrics.py` 신규 (~50 LOC, 5 tests). 기존 76 테스트 무영향 — 전체 81 passed. 후속 영향 = Task 6 의 GeminiClient 가 본 모듈을 import 하여 캐시 hit/miss/hash_change 시점에 emit 호출, Task 4 의 LLMClient Protocol 시그니처가 metrics 주입 포인트 를 노출할지 결정 (현재 plan 상으로는 GeminiClient 생성자 주입).
- **위험 카테고리**: side-effect — observer callback 이 emit() 호출 path 를 동기적으로 차단 (R-5). 베이스는 인터페이스만 제공하고 정책 (가벼움 강제) 은 docstring + 인터페이스 가이드로 약속. fail-fast 보장 안 함 (observer 예외는 호출자에게 전파되어 generate() 가 실패할 수 있음 — 베이스의 의도된 동작이고 도메인이 try/except 로 감싸야 함).
- **세부 변경 (2건)**:
  - `best_agent_base/llm/cache_metrics.py` — 신규 (`CacheEvent(StrEnum)`, `CacheObserver` alias, `CacheMetrics` 클래스 with `_observers: list`, `_counter: Counter[str]`, `add_observer()`, `emit()`, `stats()`)
  - `tests/test_cache_metrics.py` — 신규 5 cases (event_values / observer_receives_emit / stats_counter / multiple_observers_all_called / no_observers_no_error)
- **변경 전 코드**: 없음 — 신규 모듈
- **변경 후 코드** (per file)
  ```python
  # file: best_agent_base/llm/cache_metrics.py
  """CacheMetrics + Event + Observer — 캐시 적중·미적중 슬롯 (FR-6, D5).

  베이스는 인터페이스 + 카운터만. 실제 backend (Prometheus / OTel / 로깅) 는 도메인.
  observer 는 동기 callable, fire-and-forget. 무거운 backend 는 도메인이 task 분리.
  """

  from __future__ import annotations

  from collections import Counter
  from collections.abc import Callable
  from enum import StrEnum


  class CacheEvent(StrEnum):
      HIT = "hit"
      MISS = "miss"
      HASH_CHANGE = "hash_change"


  CacheObserver = Callable[[CacheEvent, str], None]
  """(event, static_hash) → None. 동기 callable, 가볍게."""


  class CacheMetrics:
      """Observer 등록 + 이벤트 emit + 누적 카운터."""

      def __init__(self) -> None:
          self._observers: list[CacheObserver] = []
          self._counter: Counter[str] = Counter()

      def add_observer(self, observer: CacheObserver) -> None:
          self._observers.append(observer)

      def emit(self, event: CacheEvent, static_hash: str) -> None:
          self._counter[event.value] += 1
          for obs in self._observers:
              obs(event, static_hash)

      def stats(self) -> dict[str, int]:
          return dict(self._counter)
  ```
  ```python
  # file: tests/test_cache_metrics.py
  """CacheMetrics + observer + event emit 검증 (FR-6, AC-6, D5)."""

  from __future__ import annotations

  from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics


  def test_event_values():
      assert CacheEvent.HIT.value == "hit"
      assert CacheEvent.MISS.value == "miss"
      assert CacheEvent.HASH_CHANGE.value == "hash_change"


  def test_observer_receives_emit():
      received: list[tuple[CacheEvent, str]] = []
      metrics = CacheMetrics()
      metrics.add_observer(lambda ev, h: received.append((ev, h)))

      metrics.emit(CacheEvent.HIT, "abc123")
      metrics.emit(CacheEvent.MISS, "def456")

      assert received == [(CacheEvent.HIT, "abc123"), (CacheEvent.MISS, "def456")]


  def test_stats_counter():
      metrics = CacheMetrics()
      metrics.emit(CacheEvent.HIT, "x")
      metrics.emit(CacheEvent.HIT, "x")
      metrics.emit(CacheEvent.MISS, "y")
      metrics.emit(CacheEvent.HASH_CHANGE, "y")

      stats = metrics.stats()
      assert stats["hit"] == 2
      assert stats["miss"] == 1
      assert stats["hash_change"] == 1


  def test_multiple_observers_all_called():
      a: list[CacheEvent] = []
      b: list[CacheEvent] = []
      metrics = CacheMetrics()
      metrics.add_observer(lambda ev, h: a.append(ev))
      metrics.add_observer(lambda ev, h: b.append(ev))

      metrics.emit(CacheEvent.HIT, "k")
      assert a == [CacheEvent.HIT]
      assert b == [CacheEvent.HIT]


  def test_no_observers_no_error():
      metrics = CacheMetrics()
      metrics.emit(CacheEvent.MISS, "k")
      assert metrics.stats()["miss"] == 1
  ```
- **검증**: `uv run pytest tests/test_cache_metrics.py -v` → 5 passed (RED→GREEN 사이클 완료). `uv run pytest -q` → 81 passed (전체 무회귀).
- **연관 항목**: CH-20260503-003 (구현계획서 — Task 3 정의), CH-20260503-005 (Task 2 CachePolicy — 같은 `best_agent_base.llm` 패키지 신규 public API 라인업)

### [2026-05-03 20:42] [코드-수정] (task: Task 4 — LLMClient Protocol + LLMResponse + TokenUsage)
- **id**: CH-20260503-007
- **이유**: D2 결정 (B-thin — `LLMClient` Protocol 얇게, `generate` + `count_tokens` 2 메서드만; 스트리밍/도구 바인딩/wide protocol 기각) 의 구현. FR-1 (provider-agnostic LLM 호출 슬롯) / AC-1 (Protocol 정의 + 신규 클래스가 `isinstance` 통과) 충족. AC-2 (GeminiClient 적합성) 는 Task 6 에서 검증. D6 (SDK 예외 그대로 전파, 에러 envelope 안 박음) 의 영향으로 `LLMResponse` 는 text + static_hash + cache_hit + usage 4 필드만. NFR-3 (`static_hash` 결정성) 는 Phase 1 `get_static_hash(ctx)` 가 source of truth — 본 모듈은 슬롯만 노출하고 hash 계산은 안 함.
- **무엇이**: best_agent_base/llm/client.py (신규), tests/test_llm_client_protocol.py (신규 — 4 cases)
- **영향범위**: `best_agent_base/llm/client.py` 신규 모듈 (~46 LOC) — `TokenUsage` (frozen, input/output/cached_tokens), `LLMResponse` (frozen, text/static_hash/cache_hit/usage), `LLMClient` (`@runtime_checkable Protocol`, `generate` async + `count_tokens` 동기). public API = 3 symbol 추가. `tests/test_llm_client_protocol.py` 신규 (~55 LOC, 4 tests). 기존 81 테스트 무영향 — 전체 85 passed. 후속 영향 = Task 5 의 `build_gemini_messages` 가 `RenderContext` → Gemini contents 변환을 담당하고, Task 6 의 `GeminiClient` 가 본 Protocol 을 구체 구현 (CachedContent + race lock + CacheMetrics emit). 도메인 (예: best_agent_invest) 는 본 Protocol 에 의존하여 mock/fake LLM 을 주입할 수 있음.
- **위험 카테고리**: breaking — 신규 public Protocol (`LLMClient`) 이 도메인 implementer 의 contract 가 됨. 향후 `generate` 시그니처 (positional `ctx`, keyword-only `cache_policy`) 또는 `count_tokens` 시그니처 변경 시 모든 도메인 구현체가 깨짐. 본 Phase 의 의도된 lock-in — B-thin 결정으로 **현재 시점에 contract 를 좁게 굳혀** 미래 wide protocol 유혹을 차단. 스트리밍/도구 바인딩이 필요해지면 별도 Protocol (예: `StreamingLLMClient`) 로 확장하여 본 Protocol 을 깨지 않는 방향이 디폴트.
- **세부 변경 (2건)**:
  - `best_agent_base/llm/client.py` — 신규 (`TokenUsage` BaseModel frozen, `LLMResponse` BaseModel frozen, `LLMClient` `@runtime_checkable Protocol` with `async generate(ctx, *, cache_policy=None) -> LLMResponse` and `count_tokens(text) -> int`)
  - `tests/test_llm_client_protocol.py` — 신규 4 cases (token_usage_frozen / llm_response_fields / protocol_runtime_checkable_compliant / protocol_runtime_checkable_noncompliant)
- **변경 전 코드**: 없음 — 신규 모듈
- **변경 후 코드** (per file)
  ```python
  # file: best_agent_base/llm/client.py
  """LLMClient Protocol + LLMResponse + TokenUsage (FR-1, D2 B-thin).

  얇은 Protocol — generate (async) + count_tokens (슬롯) 두 메서드만.
  스트리밍·도구 바인딩·에러 envelope 는 후속 Phase. (PRD §5 OOS-3..6)
  """

  from __future__ import annotations

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
      """Provider-agnostic LLM 호출 슬롯 (B-thin)."""

      async def generate(
          self,
          ctx: RenderContext,
          *,
          cache_policy: CachePolicy | None = None,
      ) -> LLMResponse: ...

      def count_tokens(self, text: str) -> int: ...
  ```
  ```python
  # file: tests/test_llm_client_protocol.py
  """LLMClient Protocol runtime_checkable 검증 (FR-1, AC-1)."""

  from __future__ import annotations

  from best_agent_base.llm.cache_policy import CachePolicy
  from best_agent_base.llm.client import LLMClient, LLMResponse, TokenUsage
  from best_agent_base.prompts.render import RenderContext


  def test_token_usage_frozen():
      u = TokenUsage(input_tokens=10, output_tokens=5)
      assert u.cached_tokens == 0
      import pytest
      from pydantic import ValidationError
      with pytest.raises(ValidationError):
          u.input_tokens = 99  # type: ignore[misc]


  def test_llm_response_fields():
      r = LLMResponse(
          text="hi",
          static_hash="abc",
          cache_hit=False,
          usage=TokenUsage(input_tokens=10, output_tokens=5),
      )
      assert r.text == "hi"
      assert r.static_hash == "abc"
      assert r.cache_hit is False
      assert r.usage.input_tokens == 10


  def test_protocol_runtime_checkable_compliant():
      class Compliant:
          async def generate(
              self, ctx: RenderContext, *, cache_policy: CachePolicy | None = None
          ) -> LLMResponse:
              return LLMResponse(
                  text="x",
                  static_hash="x",
                  cache_hit=False,
                  usage=TokenUsage(input_tokens=0, output_tokens=0),
              )

          def count_tokens(self, text: str) -> int:
              return len(text)

      assert isinstance(Compliant(), LLMClient)


  def test_protocol_runtime_checkable_noncompliant():
      class Noncompliant:
          # generate / count_tokens 둘 다 없음
          pass

      assert not isinstance(Noncompliant(), LLMClient)
  ```
- **검증**: `uv run pytest tests/test_llm_client_protocol.py -v` → 4 passed (RED→GREEN 사이클 완료). `uv run pytest -q` → 85 passed (전체 무회귀, 81 → 85).
- **연관 항목**: CH-20260503-003 (구현계획서 — Task 4 정의), CH-20260503-005 (Task 2 CachePolicy — `cache_policy: CachePolicy | None = None` 파라미터로 본 Protocol 시그니처에 직접 등장), CH-20260503-006 (Task 3 CacheMetrics — Task 6 GeminiClient 가 본 Protocol 구현 시 함께 통합)
