"""PromptSection Protocol + 7 베이스 섹션 단위 테스트."""

from __future__ import annotations

from best_agent_base.prompts.render import RenderContext
from best_agent_base.prompts.sections import (  # noqa: F401  # 6 unused = export contract check
    BASE_SECTIONS,
    DoingTasks,
    ExecutingActions,
    Intro,
    OutputEfficiency,
    PromptSection,
    System,
    ToneStyle,
    UsingTools,
)


def test_seven_sections_exist():
    """7 베이스 섹션 모두 존재 + 순서가 BASE_SECTIONS 와 일치."""
    expected_names = [
        "Intro",
        "System",
        "DoingTasks",
        "ExecutingActions",
        "UsingTools",
        "ToneStyle",
        "OutputEfficiency",
    ]
    assert [s.name for s in BASE_SECTIONS] == expected_names


def test_section_protocol_attributes():
    """각 섹션 인스턴스에 name (str), static (bool), render (callable) 존재."""
    for section in BASE_SECTIONS:
        assert isinstance(section.name, str) and section.name
        assert isinstance(section.static, bool)
        assert callable(section.render)


def test_intro_static_true():
    """§1 Intro 는 정적."""
    assert Intro.static is True


def test_section_render_returns_str():
    """render(ctx) 가 str 반환 (RenderContext 더미로)."""
    ctx = RenderContext()
    for section in BASE_SECTIONS:
        result = section.render(ctx)
        assert isinstance(result, str)


def test_protocol_runtime_check():
    """모든 베이스 섹션이 PromptSection Protocol 인스턴스로 인정."""
    for section in BASE_SECTIONS:
        # runtime_checkable Protocol — isinstance 가능
        assert isinstance(section, PromptSection)


def test_no_coding_vocab_in_intro():
    """베이스 Intro 콘텐츠가 도메인-중립 (코딩 어휘 X). NFR-3 스파이크."""
    text = Intro.render(RenderContext()).lower()
    assert "code" not in text and "python" not in text and "pep" not in text
