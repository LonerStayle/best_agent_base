"""LLM model catalog — 모델 ID 단일 정의 (raw string 사용 금지).

cogito 패턴 차용: 모델 변경 시 이 한 곳만 수정.
StrEnum 으로 타입 강제 → 잘못된 모델 ID 가 코드에 박히지 못함.
"""

from __future__ import annotations

from enum import StrEnum


class GeminiModel(StrEnum):
    """Gemini 모델 카탈로그.

    값은 그대로 모델 ID 로 사용됨 (StrEnum). 새 모델 추가 시 이 enum 에만 추가.
    """

    FLASH_LITE = "gemini-3-flash-lite"
    FLASH = "gemini-3-flash"
    PRO = "gemini-3-pro"
