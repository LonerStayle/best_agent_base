"""BOUNDARY 마커 상수 + DangerousUncached + dangerous_uncached 헬퍼.

CC 의 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 와 정확히 동일 문자열 (D1-6).
정적 영역에 의도적으로 캐시 비친화 콘텐츠를 넣을 때 본 헬퍼만 사용한다.
`reason` 인자는 기술 부채 추적용 — 빈 문자열 거부 (R-4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from best_agent_base.prompts.render import RenderContext


SYSTEM_PROMPT_DYNAMIC_BOUNDARY: str = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"


class DangerousUncached(BaseModel):
    """정적 영역에 들어가지만 의도적으로 캐시 깨는 섹션. PromptSection 만족."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    content: str
    reason: str = Field(min_length=1)
    static: bool = True

    def render(self, ctx: "RenderContext") -> str:  # noqa: ARG002
        return self.content


def dangerous_uncached(*, name: str, content: str, reason: str) -> DangerousUncached:
    """정적 영역에 캐시 비친화 콘텐츠를 넣어야 할 때만 사용.

    Args:
        name: 섹션 식별자.
        content: 렌더링 결과 문자열.
        reason: **필수** — 캐시를 의도적으로 깨는 이유 (기술 부채 추적용).
    """
    return DangerousUncached(name=name, content=content, reason=reason)
