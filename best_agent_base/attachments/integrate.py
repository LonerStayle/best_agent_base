"""call_with_attachments helper β (D3) — Phase 2 LLMClient 통합.

flow: collect_attachments → ctx.messages 합성 (prior + user_input + attachments)
      → client.generate(new_ctx)

Phase 2 LLMClient.generate(ctx, *, cache_policy) 시그니처 무변경 보존 (B-thin).
ReAct 루프 (Phase 5+) 가 본격 통합 시 본 helper 흡수.
"""

from __future__ import annotations

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient, LLMResponse
from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext


async def call_with_attachments(
    client: LLMClient,
    ctx: RenderContext,
    *,
    user_input: str,
    cache_policy: CachePolicy | None = None,
) -> LLMResponse:
    """user-turn entry helper. 어태치먼트 수집 + ctx.messages 합성 + LLM 호출.

    NFR-2 정적 캐시 안전 자동 보장 — 어태치먼트는 무조건 ctx.messages 에만 적재,
    Phase 1 BOUNDARY 위 정적 7섹션은 안 건드림.
    """
    attachment_messages = await collect_attachments(ctx, user_input=user_input)
    user_msg = Message(role="user", content=(TextBlock(text=user_input),))
    new_messages = ctx.messages + (user_msg,) + tuple(attachment_messages)
    new_ctx = ctx.model_copy(update={"messages": new_messages})
    return await client.generate(new_ctx, cache_policy=cache_policy)
