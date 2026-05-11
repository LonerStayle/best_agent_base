"""todo_reminder — 10 round 게이트 + counter + 자동 등록 (FR-8, ALL_THREAD).

CC `attachments.ts:254~257` 임계값 거울 (TURNS_SINCE_WRITE=10).
ctx.todos 본문은 박지 않음 (D6 — Phase 5+ 형식 미정 슬롯) — len() 만 본문에 포함.
"""

from __future__ import annotations

from best_agent_base.attachments.counter import count_turns_since
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message
from best_agent_base.prompts.render import RenderContext

TODO_REMINDER_THRESHOLD = 10


def _has_tool_use_named(msg: Message, name: str) -> bool:
    return any(getattr(b, "name", None) == name for b in msg.content)


class _TodoReminder:
    name = "todo_reminder"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:
        turns = count_turns_since(
            ctx.messages,
            lambda m: m.role == "assistant" and _has_tool_use_named(m, "TodoWrite"),
        )
        if turns < TODO_REMINDER_THRESHOLD:
            return None
        return (
            "The TodoWrite tool hasn't been used recently. If you're working on tasks "
            "that would benefit from tracking progress, consider using TodoWrite to "
            "track progress. Also consider cleaning up the todo list if it has become "
            "stale and no longer matches what you are working on. Only use it if it's "
            "relevant to the current work. This is just a gentle reminder — ignore if "
            "not applicable. Make sure that you NEVER mention this reminder to the user.\n\n"
            f"Current todo count: {len(ctx.todos)}"
        )


todo_reminder_attachment = _TodoReminder()
attachment_registry.register("todo_reminder", todo_reminder_attachment)
