"""NFR-4 — attachments/__init__.py + builtins/__init__.py 본체 비어있음 (D-13, AC-12)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ATTACHMENTS_INIT = (
    Path(__file__).parent.parent / "best_agent_base" / "attachments" / "__init__.py"
)
BUILTINS_INIT = (
    Path(__file__).parent.parent
    / "best_agent_base"
    / "attachments"
    / "builtins"
    / "__init__.py"
)


@pytest.mark.parametrize("init_path", [ATTACHMENTS_INIT, BUILTINS_INIT])
def test_init_is_docstring_only(init_path):
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    body = tree.body
    # docstring 1개 + 그 외 nothing
    assert len(body) == 1, f"{init_path.name} 는 docstring 만 있어야 함, body 길이={len(body)}"
    node = body[0]
    assert isinstance(node, ast.Expr), f"{init_path.name} 첫 노드는 docstring Expr 만"
    assert isinstance(node.value, ast.Constant), f"{init_path.name} docstring 만 허용"
    assert isinstance(node.value.value, str), f"{init_path.name} docstring 은 str"
