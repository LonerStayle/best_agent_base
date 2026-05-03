"""SectionRegistry 싱글톤. 7 베이스 섹션 자동 등록 + register/override.

NFR-1 (싱글톤): 모듈 로딩 시 1회만 인스턴스화.
R-1 (race): Phase 1 은 register 1회 → read-many 가정. Phase 14 멀티-요청 시점에
  ContextVar 기반 격리 재검토.
"""

from __future__ import annotations

from collections.abc import Iterable

from best_agent_base.prompts.sections import BASE_SECTIONS, PromptSection


class SectionRegistry:
    """섹션 이름 ↔ PromptSection 매핑."""

    def __init__(self) -> None:
        self._sections: dict[str, PromptSection] = {}

    def register(self, name: str, section: PromptSection) -> None:
        """섹션 콘텐츠 주입 또는 override (베이스 0줄 수정)."""
        self._sections[name] = section

    def get(self, name: str) -> PromptSection:
        """이름으로 섹션 조회. 미등록 시 KeyError."""
        return self._sections[name]

    def all_sections(self) -> Iterable[PromptSection]:
        """등록된 모든 섹션 (등록 순서). render() 의 동적 섹션 순회용."""
        return self._sections.values()


# 모듈-레벨 싱글톤 + 7 베이스 자동 등록.
registry = SectionRegistry()
for _section in BASE_SECTIONS:
    registry.register(_section.name, _section)
del _section  # 모듈 네임스페이스 클린업
