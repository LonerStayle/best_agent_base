"""D-13 — __init__.py 는 docstring-only.

re-export, side-effect, 임포트 어떤 형태도 금지. Phase 0 T6 에서 1회 발견된 위반 패턴.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
TARGET_INITS: tuple[Path, ...] = (
    PROJECT_ROOT / "best_agent_base" / "__init__.py",
    PROJECT_ROOT / "best_agent_base" / "prompts" / "__init__.py",
)


@pytest.mark.parametrize("init_path", TARGET_INITS, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_init_is_docstring_only(init_path):
    text = init_path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    body = tree.body

    # 0 statements (= empty file) 또는 1 statement (= docstring) 만 허용
    assert len(body) <= 1, (
        f"{init_path}: 본 모듈은 docstring 외 어떤 statement 도 가지면 안됩니다 (D-13). "
        f"발견된 statements: {[type(s).__name__ for s in body]}"
    )
    if len(body) == 1:
        node = body[0]
        is_docstring = (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
        assert is_docstring, (
            f"{init_path}: 단일 statement 가 docstring 이어야 합니다. 발견: {type(node).__name__}"
        )
