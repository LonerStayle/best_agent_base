"""베이스 prompts 모듈의 도메인 어휘 금칙어 검증 (NFR-3 / AC-9 / R-6).

regex `\\b` boundary 사용 → 일반 영어 단어 false fail 회피.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROMPTS_DIR = Path(__file__).parent.parent / "best_agent_base" / "prompts"

FORBIDDEN_TERMS: tuple[str, ...] = (
    # 코딩 도메인
    "PEP",
    "pytest",
    "npm",
    "type hint",
    # 의료 도메인
    "patient",
    "diagnosis",
    "HIPAA",
    # 금융 도메인
    "portfolio",
    "KYC",
)


def _scan(term: str) -> list[Path]:
    """term 을 word boundary 로 포함하는 .py 파일 목록 반환."""
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    hits: list[Path] = []
    for py in PROMPTS_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(py)
    return hits


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_prompts_module_free_of_domain_vocab(term):
    hits = _scan(term)
    assert not hits, (
        f"forbidden domain term {term!r} found in base prompts module: "
        f"{[str(h.relative_to(PROMPTS_DIR.parent.parent)) for h in hits]}"
    )


def test_prompts_dir_exists():
    """디렉토리 자체가 존재해야 검증이 의미 있음."""
    assert PROMPTS_DIR.is_dir()
