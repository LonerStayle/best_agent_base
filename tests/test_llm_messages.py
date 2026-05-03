"""split_at_boundary — Phase 1 render(ctx) 출력 → (static, dynamic) split (FR-3, AC-3)."""

from __future__ import annotations

from best_agent_base.llm.messages import split_at_boundary
from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.render import RenderContext


def test_split_at_boundary():
    static, dynamic = split_at_boundary(RenderContext())
    # 베이스에는 동적부 없음 → dynamic 은 빈 문자열
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY not in static
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY not in dynamic
    assert dynamic == ""
    assert len(static) > 0  # 베이스 7섹션은 항상 있음


def test_static_matches_render_static_part():
    """split_at_boundary 의 static = render(ctx) 의 BOUNDARY 앞 부분."""
    from best_agent_base.prompts.render import render

    rendered = render(RenderContext())
    static, dynamic = split_at_boundary(RenderContext())
    expected_static, _, expected_dynamic = rendered.partition(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    assert static == expected_static.rstrip("\n")
    assert dynamic == expected_dynamic.lstrip("\n")
