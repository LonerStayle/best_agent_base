"""LLM model catalog — 모델 ID 단일 정의 (raw string 사용 금지).

cogito 패턴 차용: 모델 변경 시 이 한 곳만 수정.
StrEnum 으로 타입 강제 → 잘못된 모델 ID 가 코드에 박히지 못함.
"""

from __future__ import annotations

from enum import StrEnum


class GeminiModel(StrEnum):
    """Gemini 모델 카탈로그 — 각 시리즈 가장 최신 1개씩.

    값은 그대로 모델 ID 로 사용됨 (StrEnum). 새 모델 추가 시 이 enum 에만 추가.

    출처: Google AI for Developers ``ai.google.dev/gemini-api/docs/models``
    (WebFetch + WebSearch 검증, 2026-05-17).

    상태:
    - Pro/Flash 는 Preview 단계 (3.x 신규 라인)
    - Flash-Lite 는 Stable (3.1)
    """

    PRO = "gemini-3.1-pro-preview"
    FLASH = "gemini-3-flash-preview"
    FLASH_LITE = "gemini-3.1-flash-lite"


class AnthropicModel(StrEnum):
    """Anthropic Claude 모델 카탈로그 — 각 시리즈 가장 최신 floating alias 만.

    값은 그대로 모델 ID 로 사용됨. dated suffix (예: ``claude-sonnet-4-5-20250929``)
    는 도메인이 직접 문자열로 박거나 enum 확장.

    출처: anthropic SDK ``anthropic/types/model.py`` (context7 검증, 2026-05-17).
    """

    OPUS_LATEST = "claude-opus-4-7"
    SONNET_LATEST = "claude-sonnet-4-6"
    HAIKU_LATEST = "claude-haiku-4-5"
