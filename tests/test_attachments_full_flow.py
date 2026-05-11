"""통합 — call_with_attachments + 베이스 디폴트 어태치먼트 + mock LLMClient (시연)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from best_agent_base.attachments.builtins import date_change as _dc  # auto-register
from best_agent_base.attachments.builtins import todo_reminder as _tr  # auto-register
from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext

_ = (_dc, _tr)


class _MockClient:
    def __init__(self) -> None:
        self.last_ctx: RenderContext | None = None

    async def generate(self, ctx, *, cache_policy=None):  # noqa: ARG002
        self.last_ctx = ctx
        return LLMResponse(
            text="ok",
            static_hash="abc123",
            cache_hit=False,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    def count_tokens(self, text):
        return len(text.split())


@pytest.mark.asyncio
async def test_full_flow_date_change_emits():
    yesterday = date.today() - timedelta(days=1)
    client = _MockClient()
    ctx = RenderContext(last_emit_date=yesterday)

    await call_with_attachments(client, ctx, user_input="안녕")

    assert client.last_ctx is not None
    texts = [b.text for m in client.last_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("date has changed" in t.lower() for t in texts)


@pytest.mark.asyncio
async def test_full_flow_todo_reminder_emits_at_threshold():
    msgs = tuple(
        Message(role="assistant", content=(TextBlock(text=f"r{i}"),))
        for i in range(10)
    )
    client = _MockClient()
    ctx = RenderContext(messages=msgs)

    await call_with_attachments(client, ctx, user_input="진행해")

    texts = [b.text for m in client.last_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("TodoWrite" in t for t in texts)


@pytest.mark.asyncio
async def test_full_flow_no_attachments_when_quiet_state():
    client = _MockClient()
    ctx = RenderContext()  # 빈 ctx, last_emit_date=None, messages=()

    await call_with_attachments(client, ctx, user_input="안녕")

    # user_input 만 추가, 어태치먼트 메시지 없음
    assert len(client.last_ctx.messages) == 1
    assert client.last_ctx.messages[0].content[0].text == "안녕"  # type: ignore[union-attr]
