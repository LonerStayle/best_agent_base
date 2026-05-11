"""Message + ContentBlock discriminated union (D2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.messages import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)


def test_text_block_frozen():
    b = TextBlock(text="hi")
    assert b.type == "text"
    assert b.text == "hi"
    with pytest.raises(ValidationError):
        b.text = "mutated"  # type: ignore[misc]


def test_tool_use_block():
    b = ToolUseBlock(id="toolu_1", name="Read", input={"file": "a.py"})
    assert b.type == "tool_use"
    assert b.input == {"file": "a.py"}


def test_tool_result_block_preserves_tool_use_id():
    b = ToolResultBlock(tool_use_id="toolu_1", content="ok")
    assert b.tool_use_id == "toolu_1"


def test_thinking_block():
    b = ThinkingBlock(text="reasoning...")
    assert b.type == "thinking"


def test_message_user_with_text_block():
    m = Message(role="user", content=(TextBlock(text="hi"),))
    assert m.role == "user"
    assert m.content[0].type == "text"


def test_message_discriminator_routes_correct_block_type():
    m = Message.model_validate(
        {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "y", "input": {}}]}
    )
    assert isinstance(m.content[0], ToolUseBlock)


def test_message_invalid_role_rejected():
    with pytest.raises(ValidationError):
        Message(role="system", content=())  # type: ignore[arg-type]
