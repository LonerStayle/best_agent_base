"""LLM 모델 카탈로그 + 프로파일 단위 테스트.

검증:
- (T1) GeminiModel StrEnum: 값이 그대로 모델 ID 문자열
- (T2) ModelProfile 기본값
- (T3) ModelProfile 검증 (temperature 범위, max_output_tokens > 0, top_p 범위)
- (T4) ModelProfile frozen (수정 불가)
- (T5) 베이스 프리셋 (DEFAULT_CHAT, DEFAULT_REASONING) 정상 인스턴스화
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.llm.models import AnthropicModel, GeminiModel
from best_agent_base.llm.profiles import DEFAULT_CHAT, DEFAULT_REASONING, ModelProfile


def test_gemini_model_is_str_enum():
    """T1: enum value = 모델 ID 문자열 (Google AI 공식 페이지 검증 2026-05-17)."""
    assert GeminiModel.PRO == "gemini-3.1-pro-preview"
    assert GeminiModel.FLASH == "gemini-3-flash-preview"
    assert GeminiModel.FLASH_LITE == "gemini-3.1-flash-lite"
    # str 비교 가능
    assert GeminiModel.FLASH.value == "gemini-3-flash-preview"
    assert isinstance(GeminiModel.FLASH, str)


def test_anthropic_model_is_str_enum():
    """T1b: AnthropicModel StrEnum — 각 시리즈 가장 최신 1개씩 (context7 검증 2026-05-17)."""
    assert AnthropicModel.OPUS_LATEST == "claude-opus-4-7"
    assert AnthropicModel.SONNET_LATEST == "claude-sonnet-4-6"
    assert AnthropicModel.HAIKU_LATEST == "claude-haiku-4-5"
    assert isinstance(AnthropicModel.SONNET_LATEST, str)
    # 정확 3개 (시리즈당 1개)
    assert len(list(AnthropicModel)) == 3


def test_model_profile_defaults():
    """T2: 필수 model 만 주면 나머지 디폴트."""
    p = ModelProfile(model=GeminiModel.FLASH)
    assert p.model == GeminiModel.FLASH
    assert p.temperature == 0.0
    assert p.max_output_tokens == 4096
    assert p.top_p is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("temperature", -0.1),
        ("temperature", 2.1),
        ("max_output_tokens", 0),
        ("max_output_tokens", -1),
        ("max_output_tokens", 32769),
        ("top_p", -0.1),
        ("top_p", 1.1),
    ],
)
def test_model_profile_field_validation(field, value):
    """T3: 잘못된 파라미터 조합은 ValidationError."""
    with pytest.raises(ValidationError):
        ModelProfile(model=GeminiModel.FLASH, **{field: value})


def test_model_profile_is_frozen():
    """T4: 인스턴스화 후 필드 수정 불가 (실수로 mutate 방지)."""
    p = ModelProfile(model=GeminiModel.FLASH)
    with pytest.raises(ValidationError):
        p.temperature = 0.5  # type: ignore[misc]


def test_default_presets():
    """T5: 베이스 프리셋이 유효한 ModelProfile 인스턴스."""
    assert isinstance(DEFAULT_CHAT, ModelProfile)
    assert DEFAULT_CHAT.model == GeminiModel.FLASH

    assert isinstance(DEFAULT_REASONING, ModelProfile)
    assert DEFAULT_REASONING.model == GeminiModel.PRO
    assert DEFAULT_REASONING.max_output_tokens == 8192


def test_raw_string_to_model_field_rejected():
    """raw string 으로 model 지정 시 enum 으로 강제됨 (또는 거부)."""
    # 알려지지 않은 모델 string 은 ValidationError
    with pytest.raises(ValidationError):
        ModelProfile(model="gemini-9-superflash")  # type: ignore[arg-type]
