"""filter_model_blocks — @[MODEL: pattern] ... @[/MODEL] 마커 런타임 필터 (Phase 3.5 D1).

CC `getAntModelOverrideSection` 백엔드 포팅. 정규식 단일 패턴 (non-greedy + DOTALL) +
fnmatch glob 매칭. 단일 레벨 마커만 허용 (중첩 = ValueError, D5).
model=None 시 모든 마커 블록 strip (조용한 정규화, D2 — Phase 1~3 backward compat).
"""

from __future__ import annotations

import fnmatch
import re

# non-greedy `.*?` + re.DOTALL = 줄바꿈 포함 + R-1 greedy 함정 회피
_MARKER_RE = re.compile(r"@\[MODEL:\s*([^\]]+?)\s*\](.*?)@\[/MODEL\]", re.DOTALL)
# 중첩 detect — 오프닝 두 번 연속 만나면 거부
_OPEN_RE = re.compile(r"@\[MODEL:\s*([^\]]+?)\s*\]")


def filter_model_blocks(text: str, model: str | None) -> str:
    """@[MODEL: pattern] ... @[/MODEL] 블록 — 매칭 시 inner keep, 미매칭 시 strip.

    model=None 시 모든 마커 블록 strip (조용한 정규화 — Phase 1~3 backward compat).
    중첩 마커 (오프닝 안 또 오프닝) 는 ValueError raise.
    """
    _detect_nested_markers(text)

    def _replace(match: re.Match[str]) -> str:
        pattern = match.group(1)
        inner = match.group(2)
        if model is None:
            return ""  # D2
        return inner if fnmatch.fnmatch(model, pattern) else ""

    return _MARKER_RE.sub(_replace, text)


def _detect_nested_markers(text: str) -> None:
    """중첩 마커 (오프닝 안 오프닝) 감지 — ValueError 즉시 raise (FR-6 / D5)."""
    depth = 0
    pos = 0
    while pos < len(text):
        open_match = _OPEN_RE.search(text, pos)
        close_idx = text.find("@[/MODEL]", pos)
        if open_match is None and close_idx == -1:
            break
        if open_match is not None and (close_idx == -1 or open_match.start() < close_idx):
            depth += 1
            if depth > 1:
                raise ValueError(
                    f"nested @[MODEL:] marker detected at offset {open_match.start()} — "
                    f"single-level only (D5)"
                )
            pos = open_match.end()
        else:
            depth -= 1
            pos = close_idx + len("@[/MODEL]")
