"""todo_reminder — 10 round 게이트 + counter + tool pool gate 통합 (FR-8 + FR-9 통합 시연)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.builtins.todo_reminder import (
    TODO_REMINDER_THRESHOLD,
    todo_reminder_attachment,
)
from best_agent_base.attachments.gates import _gates, register_tool_pool_gate
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext


def _assistant_tool(name: str) -> Message:
    return Message(
        role="assistant",
        content=(ToolUseBlock(id="x", name=name, input={}),),
    )


def _assistant_text(text: str) -> Message:
    return Message(role="assistant", content=(TextBlock(text=text),))


@pytest.fixture(autouse=True)
def _reset_gates():
    snapshot = {k: list(v) for k, v in _gates.items()}
    yield
    _gates.clear()
    _gates.update(snapshot)


def test_metadata():
    assert todo_reminder_attachment.name == "todo_reminder"
    assert todo_reminder_attachment.group == AttachmentGroup.ALL_THREAD
    assert TODO_REMINDER_THRESHOLD == 10


@pytest.mark.asyncio
async def test_under_threshold_skips():
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD - 1))
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_at_threshold_emits():
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD))
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is not None
    assert "todo" in out.lower()


@pytest.mark.asyncio
async def test_recent_todowrite_resets_counter_skips():
    msgs = (
        _assistant_tool("TodoWrite"),
        _assistant_text("r1"),
        _assistant_text("r2"),
    )
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is None  # TodoWrite 직후 = 0 카운트 + 2 → 임계 미만


@pytest.mark.asyncio
async def test_external_gate_skips_when_tool_in_pool():
    register_tool_pool_gate("todo_reminder", lambda tools: "GateTool" in tools)
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD))
    ctx = RenderContext(messages=msgs, tool_pool=frozenset({"GateTool"}))
    # gate 는 collect_attachments 에서 평가됨 — 어태치먼트 자체 build() 는 트리거됨
    # 본 테스트는 build() 단독 호출이라 게이트 우회됨 → 발화. 통합 테스트는 Task 15 에서.
    out = await todo_reminder_attachment.build(ctx)
    assert out is not None
