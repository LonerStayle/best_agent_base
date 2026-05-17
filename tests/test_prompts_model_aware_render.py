"""render(ctx) 모델 통합 — filter_model_blocks 정적/동적 양쪽 적용 (FR-4, R-2, NFR-3)."""

from __future__ import annotations

from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import (
    RenderContext,
    _render_dynamic,
    _render_static,
    get_static_hash,
)


class _ModelAwareSection:
    name = "Intro"  # override 베이스 Intro
    static = True

    def render(self, ctx):
        return "BASE @[MODEL: claude-*]CLAUDE@[/MODEL]@[MODEL: gemini-*]GEMINI@[/MODEL] TAIL"


def test_static_render_applies_filter_claude():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert "BASE CLAUDE TAIL" in out


def test_static_render_applies_filter_gemini():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext(model="gemini-2.5-flash"))
    assert "BASE GEMINI TAIL" in out


def test_static_render_model_none_strips_all():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext())  # model=None
    assert "BASE  TAIL" in out  # 모든 마커 블록 strip
    assert "CLAUDE" not in out
    assert "GEMINI" not in out


def test_hash_differs_per_model_same_ctx_shape():
    """R-2 mitigation — 같은 모델 호출 시 동일 hash, 다른 모델 다른 hash."""
    registry.register("Intro", _ModelAwareSection())
    h_claude = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    h_gemini = get_static_hash(RenderContext(model="gemini-2.5-flash"))
    h_none = get_static_hash(RenderContext())
    assert h_claude != h_gemini
    assert h_claude != h_none
    assert h_gemini != h_none


def test_hash_stable_same_model_repeated():
    registry.register("Intro", _ModelAwareSection())
    h1 = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    h2 = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert h1 == h2


def test_dynamic_render_applies_filter():
    """동적 섹션도 filter 적용."""

    class _DynamicSection:
        name = "DynamicTest"
        static = False

        def render(self, ctx):
            return "@[MODEL: claude-*]CD@[/MODEL]@[MODEL: gemini-*]GD@[/MODEL]"

    registry.register("DynamicTest", _DynamicSection())
    out = _render_dynamic(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert "CD" in out
    assert "GD" not in out
