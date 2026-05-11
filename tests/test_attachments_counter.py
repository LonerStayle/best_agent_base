"""count_turns_since — assistant turn 카운터, thinking 제외 (FR-6, AC-5, R-8)."""

from __future__ import annotations

from best_agent_base.attachments.counter import count_turns_since
from best_agent_base.messages import Message, TextBlock, ThinkingBlock, ToolUseBlock


def _user(text: str) -> Message:
    return Message(role="user", content=(TextBlock(text=text),))


def _assistant_text(text: str) -> Message:
    return Message(role="assistant", content=(TextBlock(text=text),))


def _assistant_thinking_only(text: str) -> Message:
    return Message(role="assistant", content=(ThinkingBlock(text=text),))


def _assistant_tool_use(name: str) -> Message:
    return Message(
        role="assistant",
        content=(ToolUseBlock(id="x", name=name, input={}),),
    )


def test_count_until_predicate_match():
    msgs = (
        _assistant_text("a"),
        _assistant_text("b"),
        _assistant_tool_use("TodoWrite"),  # match
        _assistant_text("c"),
        _assistant_text("d"),
    )
    n = count_turns_since(
        msgs, lambda m: m.role == "assistant" and any(
            getattr(b, "name", None) == "TodoWrite" for b in m.content
        )
    )
    assert n == 2  # c, d


def test_thinking_only_messages_excluded_from_count():
    msgs = (
        _assistant_tool_use("TodoWrite"),
        _assistant_thinking_only("reason"),
        _assistant_text("real"),
        _assistant_thinking_only("reason2"),
    )
    n = count_turns_since(
        msgs, lambda m: any(getattr(b, "name", None) == "TodoWrite" for b in m.content)
    )
    assert n == 1  # "real" only — thinking-only 2개는 카운트 안 함


def test_no_match_returns_total_assistant_count():
    msgs = (_user("hi"), _assistant_text("a"), _assistant_text("b"))
    n = count_turns_since(msgs, lambda m: False)
    assert n == 2


def test_empty_messages_returns_zero():
    assert count_turns_since((), lambda m: True) == 0
