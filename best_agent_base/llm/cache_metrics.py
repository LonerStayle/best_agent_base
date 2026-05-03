"""CacheMetrics + Event + Observer — 캐시 적중·미적중 슬롯 (FR-6, D5).

베이스는 인터페이스 + 카운터만. 실제 backend (Prometheus / OTel / 로깅) 는 도메인.
observer 는 동기 callable, fire-and-forget. 무거운 backend 는 도메인이 task 분리.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from enum import StrEnum


class CacheEvent(StrEnum):
    HIT = "hit"
    MISS = "miss"
    HASH_CHANGE = "hash_change"


CacheObserver = Callable[[CacheEvent, str], None]
"""(event, static_hash) → None. 동기 callable, 가볍게."""


class CacheMetrics:
    """Observer 등록 + 이벤트 emit + 누적 카운터."""

    def __init__(self) -> None:
        self._observers: list[CacheObserver] = []
        self._counter: Counter[str] = Counter()

    def add_observer(self, observer: CacheObserver) -> None:
        self._observers.append(observer)

    def emit(self, event: CacheEvent, static_hash: str) -> None:
        self._counter[event.value] += 1
        for obs in self._observers:
            obs(event, static_hash)

    def stats(self) -> dict[str, int]:
        return dict(self._counter)
