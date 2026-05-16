"""date_change 어태치먼트 — 자정 감지 (FR-8, AC-7)."""

from __future__ import annotations

from datetime import date

import pytest

from best_agent_base.attachments.builtins.date_change import date_change_attachment
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.prompts.render import RenderContext


def test_metadata():
    assert date_change_attachment.name == "date_change"
    assert date_change_attachment.group == AttachmentGroup.ALL_THREAD


@pytest.mark.asyncio
async def test_first_call_no_last_emit_skips():
    """last_emit_date None → 베이스라인 잡기, 발화 안 함."""
    ctx = RenderContext(last_emit_date=None)
    out = await date_change_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_same_day_skips():
    ctx = RenderContext(last_emit_date=date.today())
    out = await date_change_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_yesterday_emits_with_today_date():
    from datetime import timedelta

    yesterday = date.today() - timedelta(days=1)
    ctx = RenderContext(last_emit_date=yesterday)
    out = await date_change_attachment.build(ctx)
    assert out is not None
    assert "date has changed" in out.lower() or "날짜" in out
    assert str(date.today()) in out
