"""SectionRegistry 싱글톤 + register/override 단위 테스트."""

from __future__ import annotations

import pytest

from best_agent_base.prompts import registry as registry_module
from best_agent_base.prompts.registry import SectionRegistry, registry
from best_agent_base.prompts.render import RenderContext
from best_agent_base.prompts.sections import BASE_SECTIONS, Intro  # noqa: F401

# registry 격리는 conftest.py 의 autouse `restore_registry` fixture 가 처리.


def test_registry_is_singleton_instance():
    """모듈 로딩 시 1회 인스턴스화 — 같은 객체 (NFR-1)."""
    from best_agent_base.prompts.registry import registry as r1
    from best_agent_base.prompts.registry import registry as r2

    assert r1 is r2
    assert isinstance(registry, SectionRegistry)


def test_registry_seven_base_sections_auto_registered():
    """7 베이스 섹션이 모듈 로딩 시 자동 등록."""
    for section in BASE_SECTIONS:
        assert registry.get(section.name) is section


def test_registry_register_replaces_existing():
    """register("Intro", custom) → 해당 섹션 교체."""

    class CustomIntro:
        name = "Intro"
        static = True

        def render(self, ctx):  # noqa: ARG002
            return "custom intro"

    custom = CustomIntro()
    registry.register("Intro", custom)
    assert registry.get("Intro") is custom
    assert registry.get("Intro").render(RenderContext()) == "custom intro"


def test_registry_override_keeps_other_sections_default():
    """AC-6 — Intro override 후 나머지 6개는 베이스 기본값."""

    class CustomIntro:
        name = "Intro"
        static = True

        def render(self, ctx):  # noqa: ARG002
            return "custom"

    registry.register("Intro", CustomIntro())

    # 나머지 6개 기본값 유지
    for section in BASE_SECTIONS:
        if section.name == "Intro":
            continue
        assert registry.get(section.name) is section


def test_registry_get_unknown_raises():
    """등록되지 않은 이름 조회 → KeyError."""
    with pytest.raises(KeyError):
        registry.get("NonExistentSection")


def test_registry_module_level_singleton_idempotent():
    """import 를 N회 해도 sections dict 는 한 번만 채워짐 (re-import 시 누적 X)."""
    import importlib

    importlib.reload(registry_module)
    # 7 base only, not 14
    assert len(registry_module.registry._sections) == 7  # noqa: SLF001
