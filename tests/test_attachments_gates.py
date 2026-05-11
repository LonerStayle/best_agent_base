"""register_tool_pool_gate — predicate 등록 + OR 평가 (FR-9, AC-8, D7)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.gates import (
    _gates,  # noqa: SLF001 — 테스트에서 격리용
    is_gated,
    register_tool_pool_gate,
)


@pytest.fixture(autouse=True)
def _reset_gates():
    snapshot = {k: list(v) for k, v in _gates.items()}
    yield
    _gates.clear()
    _gates.update(snapshot)


def test_no_gate_registered_returns_false():
    assert is_gated("foo", frozenset({"Read"})) is False


def test_single_gate_true_means_gated():
    register_tool_pool_gate("todo_reminder", lambda tools: "SendUserMessage" in tools)
    assert is_gated("todo_reminder", frozenset({"SendUserMessage", "Read"})) is True
    assert is_gated("todo_reminder", frozenset({"Read"})) is False


def test_multiple_gates_or_evaluation():
    """어태치먼트당 N개 게이트, true 1개 만나면 스킵 (D7)."""
    register_tool_pool_gate("att", lambda tools: "X" in tools)
    register_tool_pool_gate("att", lambda tools: "Y" in tools)
    assert is_gated("att", frozenset({"X"})) is True  # 첫 게이트 true
    assert is_gated("att", frozenset({"Y"})) is True  # 둘째 게이트 true
    assert is_gated("att", frozenset({"X", "Y"})) is True
    assert is_gated("att", frozenset({"Z"})) is False  # 둘 다 false
