"""call_with_attachments helper β — Phase 2 LLMClient 통합 (D3, FR-3 + FR-4 통합)."""

from __future__ import annotations

from typing import Any

import pytest

from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


class _MockClient:
    def __init__(self) -> None:
        self.calls: list[tuple[RenderContext, CachePolicy | None]] = []

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        self.calls.append((ctx, cache_policy))
        return LLMResponse(
            text="ok",
            static_hash="abc123",
            cache_hit=False,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    def count_tokens(self, text: str) -> int:
        return len(text.split())


class _Fake:
    name = "fake"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
        return "attachment-data"


@pytest.mark.asyncio
async def test_helper_calls_collect_then_generate():
    attachment_registry.register("fake", _Fake())
    client = _MockClient()
    ctx = RenderContext()

    response = await call_with_attachments(client, ctx, user_input="hi")

    assert response.text == "ok"
    assert len(client.calls) == 1
    new_ctx, _ = client.calls[0]
    # ctx.messages 에 user_input + 어태치먼트 메시지 합성 검증
    texts = [b.text for m in new_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("hi" == t for t in texts)
    assert any("attachment-data" in t for t in texts)


@pytest.mark.asyncio
async def test_helper_passes_cache_policy_through():
    client = _MockClient()
    policy = CachePolicy(enabled=False)

    await call_with_attachments(client, RenderContext(), user_input="x", cache_policy=policy)

    _, passed_policy = client.calls[0]
    assert passed_policy is policy


@pytest.mark.asyncio
async def test_helper_preserves_existing_messages():
    from best_agent_base.messages import Message, TextBlock

    prior = (Message(role="user", content=(TextBlock(text="prior"),)),)
    client = _MockClient()

    await call_with_attachments(client, RenderContext(messages=prior), user_input="new")

    new_ctx, _ = client.calls[0]
    # prior + new user_input + (어태치먼트 0개)
    assert new_ctx.messages[0].content[0].text == "prior"  # type: ignore[union-attr]
    assert new_ctx.messages[1].content[0].text == "new"  # type: ignore[union-attr]
