"""LLMClient Protocol + LLMResponse + TokenUsage (FR-1, D2 B-thin).

얇은 Protocol — generate (async) + count_tokens (슬롯) 두 메서드만.
스트리밍·도구 바인딩·에러 envelope 는 후속 Phase. (PRD §5 OOS-3..6)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.prompts.render import RenderContext


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    text: str
    static_hash: str
    cache_hit: bool
    usage: TokenUsage


@runtime_checkable
class LLMClient(Protocol):
    """Provider-agnostic LLM 호출 슬롯 (B-thin)."""

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse: ...

    def count_tokens(self, text: str) -> int: ...
