"""smoosh_into_last_tool_result — in-loop 결과 + reminder 합성 (FR-7).

CC `messages.ts:1835` 거울 — 마지막 user 메시지의 마지막 tool_result 옆에
reminder text 블록 append. provider strict alternation 대응 (Gemini/Anthropic 호환).
tool_call_id 보존 — content tuple 그대로 두고 끝에 TextBlock 만 추가.
"""

from __future__ import annotations

from best_agent_base.messages import Message, TextBlock, ToolResultBlock


def _has_tool_result(msg: Message) -> bool:
    return any(isinstance(b, ToolResultBlock) for b in msg.content)


def smoosh_into_last_tool_result(
    messages: tuple[Message, ...],
    reminder_text: str,
) -> tuple[Message, ...]:
    """마지막 user 메시지가 tool_result 가지면 같은 메시지에 TextBlock append.

    없으면 별도 user 메시지로 추가. tool_call_id 는 ToolResultBlock 객체
    그대로 보존됨 (frozen, 새 메시지로 재구성).
    """
    if messages and messages[-1].role == "user" and _has_tool_result(messages[-1]):
        last = messages[-1]
        new_content = last.content + (TextBlock(text=reminder_text),)
        new_last = Message(role="user", content=new_content)
        return messages[:-1] + (new_last,)

    extra = Message(role="user", content=(TextBlock(text=reminder_text),))
    return messages + (extra,)
