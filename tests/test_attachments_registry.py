"""AttachmentRegistry — register/override/get/all_in_group (FR-5, AC-4)."""

from __future__ import annotations

from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry


class _Fake:
    def __init__(self, name: str, group: AttachmentGroup):
        self.name = name
        self.group = group

    async def build(self, ctx):  # noqa: ARG002
        return None


def test_register_and_get():
    a = _Fake("foo", AttachmentGroup.ALL_THREAD)
    attachment_registry.register("foo", a)
    assert attachment_registry.get("foo") is a


def test_override_replaces():
    first = _Fake("foo", AttachmentGroup.ALL_THREAD)
    second = _Fake("foo", AttachmentGroup.MAIN_THREAD)
    attachment_registry.register("foo", first)
    attachment_registry.override("foo", second)
    assert attachment_registry.get("foo") is second


def test_all_in_group_filters():
    a = _Fake("a", AttachmentGroup.ALL_THREAD)
    b = _Fake("b", AttachmentGroup.MAIN_THREAD)
    c = _Fake("c", AttachmentGroup.ALL_THREAD)
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    attachment_registry.register("c", c)
    in_all_thread = list(attachment_registry.all_in_group(AttachmentGroup.ALL_THREAD))
    assert {x.name for x in in_all_thread} == {"a", "c"}
