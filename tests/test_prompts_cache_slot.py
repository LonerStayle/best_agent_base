"""캐시 측정 슬롯 (get_static_hash) 단위 테스트."""

from __future__ import annotations

from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import RenderContext, get_static_hash


def test_get_static_hash_returns_16_char_hex_string():
    """sha256 hex digest 첫 16자 (D1-8)."""
    h = get_static_hash(RenderContext())
    assert isinstance(h, str)
    assert len(h) == 16
    int(h, 16)  # hex parsing 가능해야


def test_get_static_hash_deterministic_for_same_ctx():
    """AC-8 — 동일 ctx → 동일 hash (정적 안정성 1차)."""
    ctx = RenderContext()
    assert get_static_hash(ctx) == get_static_hash(ctx)


def test_get_static_hash_changes_when_static_section_replaced():
    """정적 섹션을 다른 콘텐츠로 교체하면 hash 변경.

    registry 격리는 conftest.py 의 autouse `restore_registry` fixture 가 처리.
    """
    h_before = get_static_hash(RenderContext())

    class CustomIntro:
        name = "Intro"
        static = True

        def render(self, ctx):  # noqa: ARG002
            return "completely different intro text"

    registry.register("Intro", CustomIntro())
    h_after = get_static_hash(RenderContext())
    assert h_before != h_after
