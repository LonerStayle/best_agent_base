"""베이스 prompts/llm 모듈의 도메인 어휘 금칙어 검증 (NFR-3 / AC-9 / R-6).

regex `\\b` boundary 사용 → 일반 영어 단어 false fail 회피.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "best_agent_base" / "prompts"
LLM_DIR = PROJECT_ROOT / "best_agent_base" / "llm"
ATTACHMENTS_DIR = PROJECT_ROOT / "best_agent_base" / "attachments"
MESSAGES_FILE = PROJECT_ROOT / "best_agent_base" / "messages.py"

SCAN_DIRS: tuple[Path, ...] = (PROMPTS_DIR, LLM_DIR, ATTACHMENTS_DIR)

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


def _scan(term: str, scan_dir: Path) -> list[Path]:
    """term 을 word boundary 로 포함하는 .py 파일 목록 반환."""
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    hits: list[Path] = []
    for py in scan_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(py)
    return hits


def _scan_file(term: str, file_path: Path) -> bool:
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    return bool(pattern.search(file_path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_prompts_module_free_of_domain_vocab(term):
    hits = _scan(term, PROMPTS_DIR)
    assert not hits, (
        f"forbidden domain term {term!r} found in base prompts module: "
        f"{[str(h.relative_to(PROJECT_ROOT)) for h in hits]}"
    )


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_llm_module_free_of_domain_vocab(term):
    hits = _scan(term, LLM_DIR)
    assert not hits, (
        f"forbidden domain term {term!r} found in base llm module: "
        f"{[str(h.relative_to(PROJECT_ROOT)) for h in hits]}"
    )


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_attachments_module_free_of_domain_vocab(term):
    hits = _scan(term, ATTACHMENTS_DIR)
    assert not hits, (
        f"forbidden domain term {term!r} found in base attachments module: "
        f"{[str(h.relative_to(PROJECT_ROOT)) for h in hits]}"
    )


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_messages_file_free_of_domain_vocab(term):
    assert not _scan_file(term, MESSAGES_FILE), (
        f"forbidden domain term {term!r} found in messages.py"
    )


def test_prompts_dir_exists():
    assert PROMPTS_DIR.is_dir()


def test_llm_dir_exists():
    assert LLM_DIR.is_dir()


def test_attachments_dir_exists():
    assert ATTACHMENTS_DIR.is_dir()


def test_messages_file_exists():
    assert MESSAGES_FILE.is_file()
