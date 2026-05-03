"""render(ctx) + RenderContext (skeleton — Task 4 에서 완성)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RenderContext(BaseModel):
    """베이스는 빈 모델. 도메인/Phase 가 필드 추가."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
