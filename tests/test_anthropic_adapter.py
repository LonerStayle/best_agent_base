"""AnthropicClient 어댑터 검증 (FR-7, D7 / AC-11, AC-12)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from best_agent_base.llm.anthropic import AnthropicClient
from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient
from best_agent_base.prompts.render import RenderContext


def _make_client(monkeypatch: pytest.MonkeyPatch) -> tuple[AnthropicClient, MagicMock]:
    fake_sdk = MagicMock()
    fake_sdk.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="hi", type="text")],
            usage=MagicMock(
                input_tokens=10,
                output_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
        )
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setattr(
        "best_agent_base.llm.anthropic._build_anthropic_client", lambda: fake_sdk
    )
    return AnthropicClient(model="claude-sonnet-4-5-20250929"), fake_sdk


def test_protocol_compliance(monkeypatch: pytest.MonkeyPatch):
    client, _ = _make_client(monkeypatch)
    assert isinstance(client, LLMClient)


@pytest.mark.asyncio
async def test_first_call_attaches_cache_control_marker(monkeypatch: pytest.MonkeyPatch):
    """system 메시지의 마지막 text block 에 cache_control ephemeral marker 부착 (FR-7, AC-12)."""
    client, fake = _make_client(monkeypatch)
    metrics = CacheMetrics()
    client._metrics = metrics
    events: list[CacheEvent] = []
    metrics.add_observer(lambda ev, h: events.append(ev))

    await client.generate(RenderContext())

    fake.messages.create.assert_awaited_once()
    call_kwargs = fake.messages.create.call_args.kwargs
    system = call_kwargs.get("system")
    assert isinstance(system, list)
    assert len(system) > 0
    last_block = system[-1]
    assert last_block["type"] == "text"
    assert last_block["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_cache_hit_reflected_in_response(monkeypatch: pytest.MonkeyPatch):
    """cache_read_input_tokens > 0 시 LLMResponse.cache_hit=True (AC-12)."""
    client, fake = _make_client(monkeypatch)
    fake.messages.create.return_value = MagicMock(
        content=[MagicMock(text="hi", type="text")],
        usage=MagicMock(
            input_tokens=2,  # input 작음 (대부분 cached)
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=200,  # >0 = hit
        ),
    )
    resp = await client.generate(RenderContext())
    assert resp.cache_hit is True
    assert resp.usage.cached_tokens == 200


@pytest.mark.asyncio
async def test_disabled_policy_omits_cache_control(monkeypatch: pytest.MonkeyPatch):
    client, fake = _make_client(monkeypatch)
    await client.generate(RenderContext(), cache_policy=CachePolicy(enabled=False))
    call_kwargs = fake.messages.create.call_args.kwargs
    system = call_kwargs.get("system")
    # cache_policy.enabled=False → cache_control marker 미부착
    if isinstance(system, list):
        for block in system:
            assert "cache_control" not in block


def test_count_tokens_slot_returns_int(monkeypatch: pytest.MonkeyPatch):
    client, _ = _make_client(monkeypatch)
    n = client.count_tokens("hello world")
    assert isinstance(n, int)
    assert n >= 0
