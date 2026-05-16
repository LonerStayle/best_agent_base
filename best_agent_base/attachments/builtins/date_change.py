"""date_change — OS 시계 기반 자정 감지 어태치먼트 (FR-8, ALL_THREAD)."""

from __future__ import annotations

from datetime import date

from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _DateChange:
    name = "date_change"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:
        last = ctx.last_emit_date
        today = date.today()
        if last is None:
            return None  # 베이스라인 — 첫 호출 시 발화 안 함
        if last == today:
            return None
        return (
            f"The date has changed. Today's date is now {today.isoformat()}. "
            "DO NOT mention this to the user explicitly because they are already aware."
        )


date_change_attachment = _DateChange()
attachment_registry.register("date_change", date_change_attachment)
