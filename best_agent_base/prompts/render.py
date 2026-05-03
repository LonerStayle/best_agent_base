"""render(ctx) + RenderContext + get_static_hash.

D1-7=δ: sync 영구. 도메인 비동기 fetch 는 호출자 책임.
정적 7섹션은 BOUNDARY 마커 앞, 동적부는 뒤. 마커 우연 포함 시 ValueError (R-5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.sections import BASE_SECTIONS


class RenderContext(BaseModel):
    """베이스는 빈 모델. 도메인/Phase 가 필드 추가."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)


def _render_static(ctx: RenderContext) -> str:
    """정적 7섹션 (registry 기준) 을 순서대로 렌더링.

    도메인이 베이스 섹션을 `static=False` 로 override 하면 본 루프는 건너뛰고
    `_render_dynamic` 가 그 섹션을 잡아 BOUNDARY 뒤로 옮긴다 (정적→동적 강등).
    """
    parts: list[str] = []
    for base_section in BASE_SECTIONS:
        section = registry.get(base_section.name)
        if not section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(text)
    return "\n\n".join(parts)


def _render_dynamic(ctx: RenderContext) -> str:
    """동적 섹션을 합성. 베이스에는 없음 (Phase 1).

    도메인이 `static=False` section 을 register 한 경우 또는 베이스 섹션을
    `static=False` 로 override 한 경우 모두 본 루프가 잡는다. registry 의
    `all_sections()` 는 등록 순서로 반환 (Python 3.7+ dict insertion order).
    """
    parts: list[str] = []
    for section in registry.all_sections():
        if section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(text)
    return "\n\n".join(parts)


def render(ctx: RenderContext) -> str:
    """7섹션 + BOUNDARY 마커 + 동적부 조립."""
    static = _render_static(ctx)
    dynamic = _render_dynamic(ctx)
    return f"{static}\n\n{SYSTEM_PROMPT_DYNAMIC_BOUNDARY}\n\n{dynamic}"
