"""Attachment Protocol + AttachmentGroup StrEnum (FR-1, FR-2)."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from best_agent_base.prompts.render import RenderContext


class AttachmentGroup(StrEnum):
    """3그룹 분류 (CC attachment-system.md §3그룹)."""

    USER_INPUT = "user_input"
    ALL_THREAD = "all_thread"
    MAIN_THREAD = "main_thread"


@runtime_checkable
class Attachment(Protocol):
    """베이스 / 도메인 어태치먼트 모두 만족해야 하는 Protocol.

    build() 가 None 반환 시 collect_attachments 가 자동 제외 (조건부 생성).
    """

    name: str
    group: AttachmentGroup

    async def build(self, ctx: "RenderContext") -> str | None: ...
