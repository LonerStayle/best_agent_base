"""Attachment Protocol + AttachmentGroup StrEnum (FR-1, FR-2, AC-1)."""

from __future__ import annotations

from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.prompts.render import RenderContext


def test_attachment_group_three_values():
    assert AttachmentGroup.USER_INPUT.value == "user_input"
    assert AttachmentGroup.ALL_THREAD.value == "all_thread"
    assert AttachmentGroup.MAIN_THREAD.value == "main_thread"
    assert len(list(AttachmentGroup)) == 3


def test_attachment_protocol_runtime_checkable():
    class _Fake:
        name = "x"
        group = AttachmentGroup.ALL_THREAD

        async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
            return "hello"

    assert isinstance(_Fake(), Attachment)


def test_protocol_rejects_missing_attribute():
    class _Bad:
        name = "x"
        # group missing

        async def build(self, ctx):  # noqa: ARG002
            return None

    assert not isinstance(_Bad(), Attachment)
