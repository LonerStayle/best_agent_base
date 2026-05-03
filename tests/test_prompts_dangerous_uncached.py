"""BOUNDARY 마커 상수 + DangerousUncached + dangerous_uncached 헬퍼 단위 테스트."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.prompts.boundary import (
    SYSTEM_PROMPT_DYNAMIC_BOUNDARY,
    DangerousUncached,
    dangerous_uncached,
)
from best_agent_base.prompts.render import RenderContext
from best_agent_base.prompts.sections import PromptSection


def test_boundary_constant_value():
    """CC 와 정확히 동일 문자열 (D1-6)."""
    assert SYSTEM_PROMPT_DYNAMIC_BOUNDARY == "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"


def test_dangerous_uncached_returns_pydantic_model():
    """헬퍼 호출 결과는 DangerousUncached 인스턴스."""
    obj = dangerous_uncached(name="x", content="hello", reason="unit test")
    assert isinstance(obj, DangerousUncached)
    assert obj.name == "x"
    assert obj.content == "hello"
    assert obj.reason == "unit test"


def test_dangerous_uncached_satisfies_protocol():
    """DangerousUncached 가 PromptSection Protocol 만족."""
    obj = dangerous_uncached(name="x", content="hello", reason="r")
    assert isinstance(obj, PromptSection)
    assert obj.name == "x"
    assert obj.static is True
    assert obj.render(RenderContext()) == "hello"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "x", "content": "c"},                  # reason 누락
        {"name": "x", "content": "c", "reason": ""},    # 빈 문자열
    ],
)
def test_dangerous_uncached_rejects_missing_or_empty_reason(kwargs):
    """AC-7 / R-4 — reason 필수 + min_length=1."""
    with pytest.raises((TypeError, ValidationError)):
        dangerous_uncached(**kwargs)


def test_dangerous_uncached_frozen():
    """frozen 모델 — 변경 시도는 ValidationError."""
    obj = dangerous_uncached(name="x", content="c", reason="r")
    with pytest.raises(ValidationError):
        obj.reason = "other"  # type: ignore[misc]
