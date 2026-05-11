"""도구 풀 인지 게이트 — predicate registry + OR 평가 (FR-9, D7).

어태치먼트당 N개 게이트 등록 가능. 평가는 OR — true 1개 만나면 스킵.
predicate 시그니처: (frozenset[str]) -> bool, True 반환 시 어태치먼트 비활성.

NFR-1: 베이스에 도구 이름 박지 않음 — 도메인이 predicate 안에 도구 이름 채움.
"""

from __future__ import annotations

from collections.abc import Callable

ToolPoolGate = Callable[[frozenset[str]], bool]

_gates: dict[str, list[ToolPoolGate]] = {}


def register_tool_pool_gate(attachment_name: str, predicate: ToolPoolGate) -> None:
    """게이트 등록. 같은 attachment_name 에 N개 등록 가능 (OR 평가, D7)."""
    _gates.setdefault(attachment_name, []).append(predicate)


def is_gated(attachment_name: str, tool_pool: frozenset[str]) -> bool:
    """등록된 게이트 중 하나라도 True 반환하면 스킵."""
    for predicate in _gates.get(attachment_name, ()):
        if predicate(tool_pool):
            return True
    return False
