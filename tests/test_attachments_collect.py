"""collect_attachments — 3그룹 병렬 + null 필터 + wrap + 분기 (FR-3, FR-4, AC-2, AC-3)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _Fake:
    def __init__(self, name: str, group: AttachmentGroup, output: str | None):
        self.name = name
        self.group = group
        self._output = output
        self.call_count = 0

    async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
        self.call_count += 1
        return self._output


@pytest.mark.asyncio
async def test_collect_wraps_each_in_system_reminder():
    a = _Fake("a", AttachmentGroup.ALL_THREAD, "hello")
    attachment_registry.register("a", a)
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    assert len(msgs) == 1
    text = msgs[0].content[0].text  # type: ignore[union-attr]
    assert text.startswith("<system-reminder>\n")
    assert text.endswith("\n</system-reminder>")
    assert "hello" in text


@pytest.mark.asyncio
async def test_collect_skips_none_results():
    a = _Fake("a", AttachmentGroup.ALL_THREAD, None)
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "ok")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    assert len(msgs) == 1


@pytest.mark.asyncio
async def test_user_input_none_skips_user_input_group():
    a = _Fake("a", AttachmentGroup.USER_INPUT, "skipped")
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "kept")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    msgs = await collect_attachments(RenderContext(), user_input=None)
    assert a.call_count == 0  # USER_INPUT 호출 안 됨
    assert b.call_count == 1
    assert len(msgs) == 1


@pytest.mark.asyncio
async def test_is_subagent_skips_main_thread_group():
    a = _Fake("a", AttachmentGroup.MAIN_THREAD, "skipped")
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "kept")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    await collect_attachments(RenderContext(is_subagent=True), user_input="hi")
    assert a.call_count == 0
    assert b.call_count == 1


@pytest.mark.asyncio
async def test_user_input_str_calls_all_three_groups():
    calls: dict[str, int] = {}
    for group_name in ["USER_INPUT", "ALL_THREAD", "MAIN_THREAD"]:
        att = _Fake(group_name.lower(), AttachmentGroup[group_name], "x")
        attachment_registry.register(group_name.lower(), att)
        calls[group_name] = att.call_count  # placeholder
    await collect_attachments(RenderContext(), user_input="hi")
    for name in ["user_input", "all_thread", "main_thread"]:
        assert attachment_registry.get(name).call_count == 1  # type: ignore[attr-defined]
