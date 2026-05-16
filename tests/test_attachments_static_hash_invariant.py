"""NFR-2 정적 캐시 안전 invariant — 어태치먼트 발화 전후 get_static_hash 동일 (AC-10, R-4)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from best_agent_base.attachments.builtins import date_change as _dc  # auto-register
from best_agent_base.attachments.builtins import todo_reminder as _tr  # auto-register
from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext, get_static_hash

# import 만 해서 lint warning 회피
_ = (_dc, _tr)


class _Loud:
    name = "loud"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        return "noisy attachment text " * 50  # 충분히 긴 텍스트


def test_static_hash_unchanged_by_attachment_registration():
    hash_before = get_static_hash(RenderContext())
    attachment_registry.register("loud", _Loud())
    hash_after = get_static_hash(RenderContext())
    assert hash_before == hash_after, "어태치먼트 등록만으로 정적 해시 변동 X (NFR-2)"


@pytest.mark.asyncio
async def test_static_hash_unchanged_by_attachment_emit():
    attachment_registry.register("loud", _Loud())
    yesterday = date.today() - timedelta(days=1)
    msgs = (
        Message(role="assistant", content=(ToolUseBlock(id="x", name="X", input={}),)),
    )
    ctx = RenderContext(
        messages=msgs * 12,  # todo_reminder 트리거
        last_emit_date=yesterday,  # date_change 트리거
        todos=("a", "b"),
    )
    hash_before = get_static_hash(ctx)
    msgs_out = await collect_attachments(ctx, user_input="hi")
    assert len(msgs_out) >= 1  # 어태치먼트 발화 확인
    hash_after = get_static_hash(ctx)
    assert hash_before == hash_after, "어태치먼트 발화 후도 정적 해시 변동 X"


def test_dynamic_part_does_not_leak_into_static():
    """RenderContext 슬롯에 데이터 넣어도 정적 해시 불변."""
    hash_empty = get_static_hash(RenderContext())
    hash_with_messages = get_static_hash(
        RenderContext(messages=(Message(role="user", content=(TextBlock(text="x"),)),))
    )
    hash_with_pool = get_static_hash(RenderContext(tool_pool=frozenset({"a", "b"})))
    assert hash_empty == hash_with_messages == hash_with_pool
