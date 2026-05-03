"""CachePolicy frozen 모델 — 도메인이 캐시 동작을 명시 컨트롤 (FR-5, D3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CachePolicy(BaseModel):
    """캐시 컨트롤 정책. 도메인이 generate() 호출 시 주입.

    - enabled: 캐시 사용 여부 (False 면 매 호출 신규)
    - ttl_seconds: Gemini CachedContent TTL (초)
    - force_invalidate: True 면 기존 캐시 무시하고 신규 생성
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    ttl_seconds: int = Field(default=3600, gt=0)
    force_invalidate: bool = False
