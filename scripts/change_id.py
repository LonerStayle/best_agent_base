"""
js-super:change-history 용 CH-id 생성 헬퍼.

CH-id 포맷: CH-YYYYMMDD-NNN
- 같은 feature 폴더 내 모든 *.md 파일을 스캔하여 오늘 날짜의 최대 시퀀스를 찾고 +1.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_CH_ID_RE = re.compile(r"CH-(\d{8})-(\d{3})")


def next_change_id(feature_dir: Path, today: date | None = None) -> str:
    today = today or date.today()
    date_str = today.strftime("%Y%m%d")
    max_seq = 0
    for md in feature_dir.glob("*.md"):
        for match in _CH_ID_RE.finditer(md.read_text(encoding="utf-8")):
            if match.group(1) == date_str:
                max_seq = max(max_seq, int(match.group(2)))
    return f"CH-{date_str}-{max_seq + 1:03d}"


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m scripts.change_id <feature_dir>", file=sys.stderr)
        sys.exit(2)
    print(next_change_id(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
