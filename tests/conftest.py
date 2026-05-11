"""Pytest 공통 fixtures — registry / metrics / attachment_registry 격리 (Phase 1+2+3 패턴)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.registry import attachment_registry
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


@pytest.fixture(autouse=True)
def restore_attachment_registry():
    """Phase 3 AttachmentRegistry snapshot/restore — 테스트 격리."""
    snapshot = dict(attachment_registry._attachments)  # noqa: SLF001
    try:
        yield
    finally:
        attachment_registry._attachments.clear()  # noqa: SLF001
        attachment_registry._attachments.update(snapshot)  # noqa: SLF001
