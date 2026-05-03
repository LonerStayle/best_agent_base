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
    """Fake google-genai SDK client 주입. caches.create / models.generate_content 호출 추적."""
    fake_sdk = MagicMock()
    cached_obj = MagicMock()
    cached_obj.name = "cachedContents/abc"
    fake_sdk.aio.caches.create = AsyncMock(return_value=cached_obj)
    usage_meta = MagicMock(
        prompt_token_count=10, candidates_token_count=5, cached_content_token_count=0
    )
    gen_result = MagicMock(text="hi", usage_metadata=usage_meta)
    fake_sdk.aio.models.generate_content = AsyncMock(return_value=gen_result)
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr("best_agent_base.llm.gemini._build_genai_client", lambda: fake_sdk)
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
        m = MagicMock()
        m.name = "cachedContents/abc"
        return m

    fake.aio.caches.create = AsyncMock(side_effect=slow_create)

    await asyncio.gather(*[client.generate(RenderContext()) for _ in range(5)])

    assert fake.aio.caches.create.await_count == 1


def test_count_tokens_slot_returns_int(monkeypatch: pytest.MonkeyPatch):
    """count_tokens 는 슬롯만 — Phase 9 본격 구현 전엔 conservative 추정으로 충분."""
    client, _ = _make_client(monkeypatch)
    n = client.count_tokens("hello world")
    assert isinstance(n, int)
    assert n >= 0
