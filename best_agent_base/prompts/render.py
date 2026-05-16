"""render(ctx) + RenderContext + get_static_hash.

D1-7=δ: sync 영구. 도메인 비동기 fetch 는 호출자 책임.
정적 7섹션은 BOUNDARY 마커 앞, 동적부는 뒤. 마커 우연 포함 시 ValueError (R-5).
"""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel, ConfigDict

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.sections import BASE_SECTIONS


class RenderContext(BaseModel):
    """베이스는 도메인/Phase 가 필드 추가하는 슬롯.

    Phase 3 어태치먼트 슬롯 5개 추가 — 모두 디폴트 값 보유 (R-6 backward compat):
    - messages: 대화 기록 (어태치먼트가 카운터 / smoosh 시 읽음)
    - todos: TodoWrite 도구 (Phase 5+ OOS) 슬롯, todo_reminder 가 len() 만 봄 (D6)
    - tool_pool: 현재 등록된 도구 이름 집합 (도구 풀 게이트 평가용, FR-9)
    - last_emit_date: date_change 어태치먼트 자정 감지용
    - is_subagent: True 시 MAIN_THREAD 그룹 자동 제외 (원칙 #7)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    messages: tuple = ()  # tuple[Message, ...] — Message import 시 순환 회피
    todos: tuple = ()  # tuple[Any, ...] — D6 (Phase 5+ 형식 미정 슬롯)
    tool_pool: frozenset[str] = frozenset()
    last_emit_date: date | None = None
    is_subagent: bool = False


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


def get_static_hash(ctx: RenderContext) -> str:
    """정적 섹션 묶음의 sha256 hex digest 첫 16자.

    Phase 2 의 KV 캐시 적중률 측정과 연동 (실제 측정은 Phase 2).
    """
    static_text = _render_static(ctx)
    digest = hashlib.sha256(static_text.encode("utf-8")).hexdigest()
    return digest[:16]
