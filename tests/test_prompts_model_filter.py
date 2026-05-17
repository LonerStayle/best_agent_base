"""filter_model_blocks — @[MODEL: pattern] ... @[/MODEL] 마커 필터 (FR-2/3/6, D1/D2/D5/D6, R-1)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.model_filter import filter_model_blocks


def test_match_keeps_inner_content():
    out = filter_model_blocks(
        "text @[MODEL: claude-*]ABC@[/MODEL] tail", "claude-sonnet-4-5-20250929"
    )
    assert out == "text ABC tail"


def test_mismatch_strips_block():
    out = filter_model_blocks("text @[MODEL: claude-*]ABC@[/MODEL] tail", "gemini-2.5-flash")
    assert out == "text  tail"


def test_model_none_strips_all_blocks():
    out = filter_model_blocks("@[MODEL: *]X@[/MODEL]", None)
    assert out == ""


def test_no_markers_returns_unchanged():
    out = filter_model_blocks("plain text no markers", "claude-anything")
    assert out == "plain text no markers"


def test_two_consecutive_blocks_non_greedy():
    """R-1 — greedy 매칭이면 첫 @[/MODEL] 까지가 아니라 둘째 @[/MODEL] 까지 잘못 매칭됨."""
    text = "@[MODEL: claude-*]A@[/MODEL]@[MODEL: gemini-*]B@[/MODEL]"
    out_claude = filter_model_blocks(text, "claude-sonnet-4-5-20250929")
    assert out_claude == "A"  # claude block keep, gemini block strip
    out_gemini = filter_model_blocks(text, "gemini-2.5-flash")
    assert out_gemini == "B"


def test_glob_patterns_exact():
    text = "@[MODEL: claude-sonnet-4-*]X@[/MODEL]"
    assert filter_model_blocks(text, "claude-sonnet-4-5-20250929") == "X"
    assert filter_model_blocks(text, "claude-opus-4-7") == ""


def test_wildcard_matches_any():
    assert filter_model_blocks("@[MODEL: *]X@[/MODEL]", "claude-anything") == "X"
    assert filter_model_blocks("@[MODEL: *]X@[/MODEL]", "gemini-anything") == "X"


def test_nested_marker_raises():
    """FR-6 / D5 — 중첩 마커는 구조적 모호 → ValueError."""
    text = "@[MODEL: a]@[MODEL: b]X@[/MODEL]@[/MODEL]"
    with pytest.raises(ValueError, match="nested"):
        filter_model_blocks(text, "a")


def test_multiline_block_with_dotall():
    text = "@[MODEL: claude-*]\nline1\nline2\n@[/MODEL]"
    assert filter_model_blocks(text, "claude-anything") == "\nline1\nline2\n"
