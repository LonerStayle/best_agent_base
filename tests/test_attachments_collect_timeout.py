"""collect_attachments 1초 타임아웃 + null 필터 (NFR-3, AC-11, R-7)."""

from __future__ import annotations

import asyncio
import time

import pytest

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _Slow:
    name = "slow"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        await asyncio.sleep(2.0)
        return "should never appear"


class _Fast:
    name = "fast"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        return "fast result"


@pytest.mark.asyncio
async def test_timeout_drops_slow_keeps_fast():
    attachment_registry.register("slow", _Slow())
    attachment_registry.register("fast", _Fast())
    started = time.monotonic()
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    elapsed = time.monotonic() - started
    assert elapsed < 1.5  # 1초 + 약간의 마진
    assert any("fast result" in m.content[0].text for m in msgs)  # type: ignore[union-attr]
    assert not any("should never appear" in m.content[0].text for m in msgs)  # type: ignore[union-attr]
