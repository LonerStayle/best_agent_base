"""정적 안정성 회귀 테스트 (R-3: 정적 부 hash turn-별 변동 방지)."""

from __future__ import annotations

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import RenderContext, get_static_hash, render


def test_static_part_string_is_stable_over_n_calls():
    """동일 ctx, 베이스 registry → 정적부 문자열 N회 동일."""
    ctx = RenderContext()
    static_outputs = [render(ctx).split(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)[0] for _ in range(10)]
    assert len(set(static_outputs)) == 1


def test_static_hash_is_stable_over_n_calls():
    """get_static_hash N회 동일."""
    ctx = RenderContext()
    hashes = [get_static_hash(ctx) for _ in range(10)]
    assert len(set(hashes)) == 1


def test_full_render_static_part_unchanged_when_only_dynamic_changes():
    """동적 섹션이 추가/변경되어도 정적 hash 는 영향 받지 않음."""
    snapshot = dict(registry._sections)  # noqa: SLF001
    try:
        ctx = RenderContext()
        h_before = get_static_hash(ctx)

        class DynamicTimestamp:
            name = "DynamicTimestamp"
            static = False

            def render(self, ctx):  # noqa: ARG002
                import time

                return f"now: {time.time()}"

        registry.register("DynamicTimestamp", DynamicTimestamp())
        h_after = get_static_hash(ctx)
        assert h_before == h_after, "static hash must NOT depend on dynamic sections"
    finally:
        registry._sections.clear()  # noqa: SLF001
        registry._sections.update(snapshot)  # noqa: SLF001
