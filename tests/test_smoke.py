"""Phase 0 import 무결성 스모크 테스트.

9개 서브패키지 + config 가 모두 import 가능해야 한다.
"""

import importlib

import pytest

SUBPACKAGES = [
    "best_agent_base.core",
    "best_agent_base.prompts",
    "best_agent_base.attachments",
    "best_agent_base.tools",
    "best_agent_base.hitl",
    "best_agent_base.llm",
    "best_agent_base.context",
    "best_agent_base.api",
    "best_agent_base.db",
    "best_agent_base.config",
]


@pytest.mark.parametrize("module_name", SUBPACKAGES)
def test_subpackage_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_top_level_aggregate_import() -> None:
    from best_agent_base import (  # noqa: F401
        api,
        attachments,
        config,
        context,
        core,
        db,
        hitl,
        llm,
        prompts,
        tools,
    )
