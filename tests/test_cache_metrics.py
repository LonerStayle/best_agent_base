"""CacheMetrics + observer + event emit 검증 (FR-6, AC-6, D5)."""

from __future__ import annotations

from best_agent_base.llm.cache_metrics import CacheEvent, CacheMetrics


def test_event_values():
    assert CacheEvent.HIT.value == "hit"
    assert CacheEvent.MISS.value == "miss"
    assert CacheEvent.HASH_CHANGE.value == "hash_change"


def test_observer_receives_emit():
    received: list[tuple[CacheEvent, str]] = []
    metrics = CacheMetrics()
    metrics.add_observer(lambda ev, h: received.append((ev, h)))

    metrics.emit(CacheEvent.HIT, "abc123")
    metrics.emit(CacheEvent.MISS, "def456")

    assert received == [(CacheEvent.HIT, "abc123"), (CacheEvent.MISS, "def456")]


def test_stats_counter():
    metrics = CacheMetrics()
    metrics.emit(CacheEvent.HIT, "x")
    metrics.emit(CacheEvent.HIT, "x")
    metrics.emit(CacheEvent.MISS, "y")
    metrics.emit(CacheEvent.HASH_CHANGE, "y")

    stats = metrics.stats()
    assert stats["hit"] == 2
    assert stats["miss"] == 1
    assert stats["hash_change"] == 1


def test_multiple_observers_all_called():
    a: list[CacheEvent] = []
    b: list[CacheEvent] = []
    metrics = CacheMetrics()
    metrics.add_observer(lambda ev, h: a.append(ev))
    metrics.add_observer(lambda ev, h: b.append(ev))

    metrics.emit(CacheEvent.HIT, "k")
    assert a == [CacheEvent.HIT]
    assert b == [CacheEvent.HIT]


def test_no_observers_no_error():
    metrics = CacheMetrics()
    metrics.emit(CacheEvent.MISS, "k")
    assert metrics.stats()["miss"] == 1
