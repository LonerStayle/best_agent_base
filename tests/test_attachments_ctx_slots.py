"""RenderContext 신규 슬롯 5개 — 디폴트 값 검증 + Phase 1/2 backward compat (R-6)."""

from __future__ import annotations

from datetime import date

from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext


def test_default_constructor_no_args():
    """인자 0개 호출 가능 (Phase 1/2 회귀 방지)."""
    ctx = RenderContext()
    assert ctx.messages == ()
    assert ctx.todos == ()
    assert ctx.tool_pool == frozenset()
    assert ctx.last_emit_date is None
    assert ctx.is_subagent is False


def test_messages_slot_accepts_tuple():
    msg = Message(role="user", content=(TextBlock(text="hi"),))
    ctx = RenderContext(messages=(msg,))
    assert len(ctx.messages) == 1
    assert ctx.messages[0].role == "user"


def test_tool_pool_frozenset():
    ctx = RenderContext(tool_pool=frozenset({"Read", "Edit"}))
    assert "Read" in ctx.tool_pool


def test_last_emit_date_optional():
    ctx = RenderContext(last_emit_date=date(2026, 5, 10))
    assert ctx.last_emit_date == date(2026, 5, 10)


def test_is_subagent_boolean():
    ctx = RenderContext(is_subagent=True)
    assert ctx.is_subagent is True


def test_frozen_after_construction():
    import pytest
    from pydantic import ValidationError

    ctx = RenderContext()
    with pytest.raises(ValidationError):
        ctx.is_subagent = True  # type: ignore[misc]
