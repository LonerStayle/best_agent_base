"""Pytest 공통 fixtures — registry / metrics 격리 (Phase 1+2 패턴)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.registry import registry


@pytest.fixture(autouse=True)
def restore_registry():
    """Phase 1 SectionRegistry snapshot/restore — 4 테스트 파일 중복 DRY."""
    snapshot = dict(registry._sections)  # noqa: SLF001 — test fixture 한정
    try:
        yield
    finally:
        registry._sections.clear()  # noqa: SLF001
        registry._sections.update(snapshot)  # noqa: SLF001
