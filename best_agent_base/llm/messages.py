"""Phase 1 render(ctx) → provider 메시지 구조 변환 (FR-3).

BOUNDARY 마커 기준 (static, dynamic) 으로 정확히 split. 정적부 = 캐시 대상.
provider-agnostic — Gemini / Anthropic 어댑터 모두 재사용.
"""

from __future__ import annotations

from best_agent_base.prompts.boundary import SYSTEM_PROMPT_DYNAMIC_BOUNDARY
from best_agent_base.prompts.render import RenderContext, render


def split_at_boundary(ctx: RenderContext) -> tuple[str, str]:
    """Returns (static_text, dynamic_text), split at SYSTEM_PROMPT_DYNAMIC_BOUNDARY.

    Phase 1 `render(ctx)` 출력은 "<static>\n\n<BOUNDARY>\n\n<dynamic>" 형식.
    정확히 BOUNDARY 마커에서 분리해 trailing/leading whitespace 만 정리.
    provider-agnostic — Gemini / Anthropic 어댑터 모두 동일 split 재사용.
    """
    rendered = render(ctx)
    static_part, _, dynamic_part = rendered.partition(SYSTEM_PROMPT_DYNAMIC_BOUNDARY)
    return static_part.rstrip("\n"), dynamic_part.lstrip("\n")
