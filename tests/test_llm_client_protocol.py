"""LLMClient Protocol runtime_checkable 검증 (FR-1, AC-1)."""

from __future__ import annotations

from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient, LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


def test_token_usage_frozen():
    u = TokenUsage(input_tokens=10, output_tokens=5)
    assert u.cached_tokens == 0
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        u.input_tokens = 99  # type: ignore[misc]


def test_llm_response_fields():
    r = LLMResponse(
        text="hi",
        static_hash="abc",
        cache_hit=False,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    assert r.text == "hi"
    assert r.static_hash == "abc"
    assert r.cache_hit is False
    assert r.usage.input_tokens == 10


def test_protocol_runtime_checkable_compliant():
    class Compliant:
        async def generate(
            self, ctx: RenderContext, *, cache_policy: CachePolicy | None = None
        ) -> LLMResponse:
            return LLMResponse(
                text="x",
                static_hash="x",
                cache_hit=False,
                usage=TokenUsage(input_tokens=0, output_tokens=0),
            )

        def count_tokens(self, text: str) -> int:
            return len(text)

    assert isinstance(Compliant(), LLMClient)


def test_protocol_runtime_checkable_noncompliant():
    class Noncompliant:
        # generate / count_tokens 둘 다 없음
        pass

    assert not isinstance(Noncompliant(), LLMClient)
