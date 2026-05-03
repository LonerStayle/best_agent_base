"""캐시 키 결정성 검증 (NFR-3, AC-7) — 동일 ctx → 동일 key, N=10 안정."""

from __future__ import annotations

from best_agent_base.llm.gemini import _cache_key_for
from best_agent_base.prompts.render import RenderContext


def test_same_ctx_same_key_n10():
    ctx = RenderContext()
    keys = {_cache_key_for(ctx) for _ in range(10)}
    assert len(keys) == 1
