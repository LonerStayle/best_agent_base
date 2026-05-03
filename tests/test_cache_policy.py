"""CachePolicy frozen 모델 검증 (FR-5, AC-5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.llm.cache_policy import CachePolicy


def test_default_policy_enabled():
    p = CachePolicy()
    assert p.enabled is True
    assert p.ttl_seconds == 3600
    assert p.force_invalidate is False


def test_disabled_policy():
    p = CachePolicy(enabled=False)
    assert p.enabled is False


def test_force_invalidate():
    p = CachePolicy(force_invalidate=True)
    assert p.force_invalidate is True


def test_custom_ttl():
    p = CachePolicy(ttl_seconds=60)
    assert p.ttl_seconds == 60


def test_frozen_immutable():
    p = CachePolicy()
    with pytest.raises(ValidationError):
        p.enabled = False  # type: ignore[misc]


def test_negative_ttl_rejected():
    with pytest.raises(ValidationError):
        CachePolicy(ttl_seconds=-1)
