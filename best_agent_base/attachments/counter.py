"""assistant turn 카운터 (FR-6).

CC `attachments.ts:3215~3263` 거울 — 비-thinking assistant 메시지만 카운트.
predicate 만족 메시지 발견 시 종료, 없으면 전체 카운트 반환.
"""

from __future__ import annotations

from collections.abc import Callable

from best_agent_base.messages import Message


def _is_thinking_only(msg: Message) -> bool:
    return all(b.type == "thinking" for b in msg.content)


def count_turns_since(
    messages: tuple[Message, ...],
    predicate: Callable[[Message], bool],
) -> int:
    """messages 끝부터 거꾸로 훑으면서 비-thinking assistant 카운트.

    predicate(msg)=True 만나면 종료, 못 만나면 전체 비-thinking assistant 수.
    thinking-only assistant 메시지는 카운트에서 제외 (R-8).
    """
    count = 0
    for msg in reversed(messages):
        if msg.role != "assistant":
            continue
        if _is_thinking_only(msg):
            continue
        if predicate(msg):
            return count
        count += 1
    return count
