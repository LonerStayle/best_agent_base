"""Anthropic 어댑터 — anthropic SDK 직접, cache_control ephemeral marker 통합 (FR-7, D7).

system 메시지의 마지막 text block 에
`{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}` 부착으로
server-side prompt caching 트리거. CachePolicy.enabled=False 면 marker 미부착.
SDK 예외는 그대로 전파 (D6).
"""

from __future__ import annotations

import os

from anthropic import AsyncAnthropic

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.llm.messages import split_at_boundary
from best_agent_base.llm.models import AnthropicModel
from best_agent_base.prompts.render import RenderContext, get_static_hash


def _build_anthropic_client() -> AsyncAnthropic:
    """AsyncAnthropic SDK Client. 테스트에서 monkeypatch 가능."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 환경 변수가 설정되어 있지 않습니다.")
    return AsyncAnthropic(api_key=api_key)


class AnthropicClient:
    """LLMClient 적합 Anthropic 참조 구현.

    캐싱: system 메시지의 마지막 text block 에 cache_control ephemeral marker 부착 (D7).
    server-side hash 매칭으로 자동 hit. 적중 시 응답의 usage.cache_read_input_tokens > 0.
    """

    def __init__(
        self,
        *,
        model: str = AnthropicModel.SONNET_LATEST.value,
        max_tokens: int = 4096,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._metrics = metrics if metrics is not None else CacheMetrics()
        self._sdk = _build_anthropic_client()
        self._last_hash: str | None = None

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        """Phase 1 render(ctx) 출력을 Anthropic Messages API 로 호출, 캐싱 정책 반영.

        Raises: anthropic SDK 예외 (BadRequestError / RateLimitError / etc.) 그대로 전파 (D6).
        에러 envelope 변환은 도구 베이스 Phase 의 본질이라 본 어댑터에서 흡수하지 않음.
        Phase 3.5: ctx.model 없으면 self._model 자동 주입 (D3, FR-5).
        """
        # Phase 3.5 — ctx.model 없으면 자기 model 자동 주입
        if ctx.model is None:
            ctx = ctx.model_copy(update={"model": self._model})
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
        key = get_static_hash(ctx)

        # HASH_CHANGE 가시성 (R-2). 메트릭 계약: HASH_CHANGE 는 같은 호출 안의 후속
        # MISS 와 union 으로 발생 (Gemini 어댑터 동일) — observer 합산 시 overcount 주의.
        if self._last_hash is not None and self._last_hash != key:
            self._metrics.emit(CacheEvent.HASH_CHANGE, key)
        self._last_hash = key

        # system 메시지 구성 — cache_policy.enabled 면 마지막 block 에 cache_control 부착.
        # force_invalidate=True 는 marker 미부착 (= disabled 와 동일 효과). Anthropic 은
        # client-side invalidate API 가 없어 marker 미부착으로 server-side cache skip 효과 (D7).
        system_block: dict = {"type": "text", "text": static_text}
        if policy.enabled and not policy.force_invalidate:
            system_block["cache_control"] = {"type": "ephemeral"}

        result = await self._sdk.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[system_block],
            messages=[{"role": "user", "content": dynamic_text or " "}],
        )

        usage_meta = getattr(result, "usage", None)
        cache_read = getattr(usage_meta, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(usage_meta, "cache_creation_input_tokens", 0) or 0
        cache_hit = cache_read > 0

        # 메트릭 emit
        if policy.enabled:
            self._metrics.emit(CacheEvent.HIT if cache_hit else CacheEvent.MISS, key)

        # 응답 텍스트 추출 (content[0].text — context7 검증됨)
        text = ""
        content = getattr(result, "content", None)
        if content and len(content) > 0:
            first = content[0]
            text = getattr(first, "text", "") or ""

        usage = TokenUsage(
            input_tokens=getattr(usage_meta, "input_tokens", 0) or 0,
            output_tokens=getattr(usage_meta, "output_tokens", 0) or 0,
            cached_tokens=cache_read or cache_creation,
        )

        return LLMResponse(
            text=text,
            static_hash=key,
            cache_hit=cache_hit,
            usage=usage,
        )

    def count_tokens(self, text: str) -> int:
        # Phase 9 본격 — 현재는 conservative 추정
        return int(len(text.split()) * 1.3)
