"""render(ctx) 정렬 + BOUNDARY 삽입 + 마커 충돌 검사 단위 테스트."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import RenderContext, render


@pytest.fixture(autouse=True)
def restore_registry():
    snapshot = dict(registry._sections)  # noqa: SLF001
    yield
    registry._sections.clear()  # noqa: SLF001
    registry._sections.update(snapshot)  # noqa: SLF001


def test_render_returns_str():
    """AC-1 — render(ctx) 가 str 반환."""
    output = render(RenderContext())
    assert isinstance(output, str)


def test_render_contains_boundary_exactly_once():
    """AC-3 — BOUNDARY 마커가 정확히 1회 등장."""
    output = render(RenderContext())
    assert output.count(SYSTEM_PROMPT_DYNAMIC_BOUNDARY) == 1


def test_render_static_before_boundary_dynamic_after():
    """AC-4 — 마커 앞에 정적 7섹션, 뒤에 동적 부."""
    output = render(RenderContext())
    static_part, dynamic_part = output.split(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)

    # 7 섹션의 베이스 텍스트 일부가 정적부에 포함
    assert "assistant agent" in static_part  # Intro
    assert "Operating environment" in static_part  # System
    # 동적부는 비어있을 수도, 짧을 수도 있음 (Phase 1 = 동적 콘텐츠 없음)
    # 단, 마커 앞에 위치하지 않음을 보장
    if dynamic_part.strip():
        assert "assistant agent" not in dynamic_part


def test_render_section_order_matches_base_sections():
    """7 섹션이 BASE_SECTIONS 순서대로 정적부에 등장."""
    output = render(RenderContext())
    static_part = output.split(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)[0]
    indices = [
        static_part.find("assistant agent"),
        static_part.find("Operating environment"),
        static_part.find("step-by-step"),
        static_part.find("irreversible"),
        static_part.find("dedicated tools"),
        static_part.find("Keep responses concise"),
        static_part.find("Lead with actions"),
    ]
    # 모두 발견되어야
    assert all(i >= 0 for i in indices)
    # 단조 증가 (순서)
    assert indices == sorted(indices)


def test_render_rejects_marker_in_domain_content():
    """R-5 — 도메인 섹션이 마커를 콘텐츠에 우연히 포함하면 ValueError."""

    class EvilIntro:
        name = "Intro"
        static = True

        def render(self, ctx):  # noqa: ARG002
            return f"oops {SYSTEM_PROMPT_DYNAMIC_BOUNDARY} more text"

    registry.register("Intro", EvilIntro())
    with pytest.raises(ValueError, match="boundary marker"):
        render(RenderContext())
