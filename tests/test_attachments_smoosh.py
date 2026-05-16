"""smoosh_into_last_tool_result — in-loop 결과 + reminder 합성 (FR-7, AC-6, R-5)."""

from __future__ import annotations

from best_agent_base.attachments.smoosh import smoosh_into_last_tool_result
from best_agent_base.messages import Message, TextBlock, ToolResultBlock


def _user_with_tool_result(tool_use_id: str, content: str) -> Message:
    return Message(
        role="user",
        content=(ToolResultBlock(tool_use_id=tool_use_id, content=content),),
    )


def _user_text(text: str) -> Message:
    return Message(role="user", content=(TextBlock(text=text),))


def test_smoosh_appends_text_block_to_last_user_message():
    msgs = (_user_with_tool_result("toolu_1", "result A"),)
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out) == 1
    last = out[-1]
    assert len(last.content) == 2
    assert isinstance(last.content[0], ToolResultBlock)
    assert last.content[0].tool_use_id == "toolu_1"  # 보존
    assert isinstance(last.content[1], TextBlock)
    assert last.content[1].text == "<system-reminder>x</system-reminder>"


def test_no_tool_result_appends_separate_user_message():
    msgs = (_user_text("hi"),)
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out) == 2
    assert out[1].role == "user"
    assert isinstance(out[1].content[0], TextBlock)


def test_multiple_tool_results_only_last_user_msg_smooshed():
    msgs = (
        _user_with_tool_result("toolu_1", "A"),
        _user_with_tool_result("toolu_2", "B"),
    )
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out[0].content) == 1  # 첫 user 변경 없음
    assert len(out[1].content) == 2  # 마지막 user 에만 reminder 합성


def test_empty_messages_returns_separate_user_message():
    out = smoosh_into_last_tool_result((), "<system-reminder>x</system-reminder>")
    assert len(out) == 1
    assert out[0].role == "user"
