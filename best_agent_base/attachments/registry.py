"""AttachmentRegistry 싱글톤 (FR-5, D8 — Phase 1 SectionRegistry 패턴 거울).

R-1 (race): register 1회 → read-many 가정. Phase 14 ContextVar 재검토.
"""

from __future__ import annotations

from collections.abc import Iterable

from best_agent_base.attachments.protocol import Attachment, AttachmentGroup


class AttachmentRegistry:
    """name ↔ Attachment 매핑."""

    def __init__(self) -> None:
        self._attachments: dict[str, Attachment] = {}

    def register(self, name: str, attachment: Attachment) -> None:
        self._attachments[name] = attachment

    def override(self, name: str, attachment: Attachment) -> None:
        """alias of register — 의도 명시적."""
        self._attachments[name] = attachment

    def get(self, name: str) -> Attachment:
        return self._attachments[name]

    def all_in_group(self, group: AttachmentGroup) -> Iterable[Attachment]:
        return (a for a in self._attachments.values() if a.group == group)


attachment_registry = AttachmentRegistry()
