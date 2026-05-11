"""Message + ContentBlock discriminated union (Phase 3 D2).

Anthropic content block 구조 거울 — Phase 2 어댑터 호환.
모든 모델 frozen — Phase 1/2 패턴 일관.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class TextBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str  # MVP — block list 는 후속 Phase


class ThinkingBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["thinking"] = "thinking"
    text: str


ContentBlock = Annotated[
    Union[TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock],
    Field(discriminator="type"),
]


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: Literal["user", "assistant"]
    content: tuple[ContentBlock, ...]
