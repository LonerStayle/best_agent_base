---
commit_policy: per-task
---

# Phase 3 어태치먼트 시스템 구현계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code 의 30+ 종 자동 첨부 메커니즘을 베이스 골격(Protocol + 3그룹 + system-reminder wrap + 카운터 + smoosh + 도구 풀 게이트 + 베이스 디폴트 2종 + helper)으로 포팅한다.

**Architecture:** 도메인 → `call_with_attachments(client, ctx, user_input)` helper → `collect_attachments` (asyncio.gather 1초) + Phase 2 `client.generate(new_ctx)` 분기. 어태치먼트는 항상 `ctx.messages` 에만 적재 (NFR-2 정적 캐시 안전 invariant 보장). 베이스 디폴트 어태치먼트(`date_change`, `todo_reminder`)가 메커니즘 즉시 시연.

**Tech Stack:** Python 3.12+, Pydantic 2 frozen models, asyncio, pytest + pytest-asyncio, ruff.

**Spec inputs:**
- `phase-3-attachments-requirements.md` (CH-20260508-001) — FR-1..9 + NFR-1..4 + AC-1..12 + OOS 8
- `phase-3-attachments-tech-design.md` (CH-20260510-001) — D1..D10 결정 + R-1..R-8 리스크 + 16 테스트 파일

---

## 1. 단계별 작업

### Task 1: Message + ContentBlock 데이터 모델

**Files:**
- Create: `best_agent_base/messages.py`
- Test: `tests/test_messages.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_messages.py
"""Message + ContentBlock discriminated union (D2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from best_agent_base.messages import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)


def test_text_block_frozen():
    b = TextBlock(text="hi")
    assert b.type == "text"
    assert b.text == "hi"
    with pytest.raises(ValidationError):
        b.text = "mutated"  # type: ignore[misc]


def test_tool_use_block():
    b = ToolUseBlock(id="toolu_1", name="Read", input={"file": "a.py"})
    assert b.type == "tool_use"
    assert b.input == {"file": "a.py"}


def test_tool_result_block_preserves_tool_use_id():
    b = ToolResultBlock(tool_use_id="toolu_1", content="ok")
    assert b.tool_use_id == "toolu_1"


def test_thinking_block():
    b = ThinkingBlock(text="reasoning...")
    assert b.type == "thinking"


def test_message_user_with_text_block():
    m = Message(role="user", content=(TextBlock(text="hi"),))
    assert m.role == "user"
    assert m.content[0].type == "text"


def test_message_discriminator_routes_correct_block_type():
    m = Message.model_validate(
        {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "y", "input": {}}]}
    )
    assert isinstance(m.content[0], ToolUseBlock)


def test_message_invalid_role_rejected():
    with pytest.raises(ValidationError):
        Message(role="system", content=())  # type: ignore[arg-type]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_messages.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'best_agent_base.messages'`

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/messages.py
"""Message + ContentBlock discriminated union (Phase 3 D2).

Anthropic content block 구조 거울 — Phase 2 어댑터 호환.
모든 모델 frozen — Phase 1/2 패턴 일관.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class TextBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str  # MVP — block list 는 후속 Phase


class ThinkingBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["thinking"] = "thinking"
    text: str


ContentBlock = Annotated[
    Union[TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock],
    Field(discriminator="type"),
]


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: Literal["user", "assistant"]
    content: tuple[ContentBlock, ...]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_messages.py -v`
Expected: PASS — 7/7 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/messages.py tests/test_messages.py
git commit -m "feat(messages): Message + ContentBlock discriminated union (FR Task 1)"
```

---

### Task 2: attachments/ 패키지 골격 + Protocol + AttachmentGroup

**Files:**
- Create: `best_agent_base/attachments/__init__.py`
- Create: `best_agent_base/attachments/protocol.py`
- Test: `tests/test_attachments_protocol.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_protocol.py
"""Attachment Protocol + AttachmentGroup StrEnum (FR-1, FR-2, AC-1)."""

from __future__ import annotations

from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.prompts.render import RenderContext


def test_attachment_group_three_values():
    assert AttachmentGroup.USER_INPUT.value == "user_input"
    assert AttachmentGroup.ALL_THREAD.value == "all_thread"
    assert AttachmentGroup.MAIN_THREAD.value == "main_thread"
    assert len(list(AttachmentGroup)) == 3


def test_attachment_protocol_runtime_checkable():
    class _Fake:
        name = "x"
        group = AttachmentGroup.ALL_THREAD

        async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
            return "hello"

    assert isinstance(_Fake(), Attachment)


def test_protocol_rejects_missing_attribute():
    class _Bad:
        name = "x"
        # group missing

        async def build(self, ctx):  # noqa: ARG002
            return None

    assert not isinstance(_Bad(), Attachment)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_protocol.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'best_agent_base.attachments'`

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/attachments/__init__.py
"""Phase 3 어태치먼트 시스템 — Protocol + 3그룹 분류 + 병렬 수집 + 베이스 디폴트 2종.

D-13: docstring-only. 실제 객체는 서브모듈에서 import.
"""
```

```python
# best_agent_base/attachments/protocol.py
"""Attachment Protocol + AttachmentGroup StrEnum (FR-1, FR-2)."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from best_agent_base.prompts.render import RenderContext


class AttachmentGroup(StrEnum):
    """3그룹 분류 (CC attachment-system.md §3그룹)."""

    USER_INPUT = "user_input"
    ALL_THREAD = "all_thread"
    MAIN_THREAD = "main_thread"


@runtime_checkable
class Attachment(Protocol):
    """베이스 / 도메인 어태치먼트 모두 만족해야 하는 Protocol.

    build() 가 None 반환 시 collect_attachments 가 자동 제외 (조건부 생성).
    """

    name: str
    group: AttachmentGroup

    async def build(self, ctx: "RenderContext") -> str | None: ...
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_protocol.py -v`
Expected: PASS — 3/3 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/__init__.py best_agent_base/attachments/protocol.py tests/test_attachments_protocol.py
git commit -m "feat(attachments): Protocol + AttachmentGroup (FR-1/2 Task 2)"
```

---

### Task 3: AttachmentRegistry 싱글톤 + conftest snapshot fixture

**Files:**
- Create: `best_agent_base/attachments/registry.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_attachments_registry.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_registry.py
"""AttachmentRegistry — register/override/get/all_in_group (FR-5, AC-4)."""

from __future__ import annotations

from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry


class _Fake:
    def __init__(self, name: str, group: AttachmentGroup):
        self.name = name
        self.group = group

    async def build(self, ctx):  # noqa: ARG002
        return None


def test_register_and_get():
    a = _Fake("foo", AttachmentGroup.ALL_THREAD)
    attachment_registry.register("foo", a)
    assert attachment_registry.get("foo") is a


def test_override_replaces():
    first = _Fake("foo", AttachmentGroup.ALL_THREAD)
    second = _Fake("foo", AttachmentGroup.MAIN_THREAD)
    attachment_registry.register("foo", first)
    attachment_registry.override("foo", second)
    assert attachment_registry.get("foo") is second


def test_all_in_group_filters():
    a = _Fake("a", AttachmentGroup.ALL_THREAD)
    b = _Fake("b", AttachmentGroup.MAIN_THREAD)
    c = _Fake("c", AttachmentGroup.ALL_THREAD)
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    attachment_registry.register("c", c)
    in_all_thread = list(attachment_registry.all_in_group(AttachmentGroup.ALL_THREAD))
    assert {x.name for x in in_all_thread} == {"a", "c"}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현 — registry.py + conftest 확장**

```python
# best_agent_base/attachments/registry.py
"""AttachmentRegistry 싱글톤 (FR-5, D8 — Phase 1 SectionRegistry 패턴 거울).

R-1 (race): register 1회 → read-many 가정. Phase 14 ContextVar 재검토.
"""

from __future__ import annotations

from collections.abc import Iterable

from best_agent_base.attachments.protocol import Attachment, AttachmentGroup


class AttachmentRegistry:
    """name ↔ Attachment 매핑."""

    def __init__(self) -> None:
        self._attachments: dict[str, Attachment] = {}

    def register(self, name: str, attachment: Attachment) -> None:
        self._attachments[name] = attachment

    def override(self, name: str, attachment: Attachment) -> None:
        """alias of register — 의도 명시적."""
        self._attachments[name] = attachment

    def get(self, name: str) -> Attachment:
        return self._attachments[name]

    def all_in_group(self, group: AttachmentGroup) -> Iterable[Attachment]:
        return (a for a in self._attachments.values() if a.group == group)


attachment_registry = AttachmentRegistry()
```

**원본** (`tests/conftest.py`):

```python
"""Pytest 공통 fixtures — registry / metrics 격리 (Phase 1+2 패턴)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.registry import registry


@pytest.fixture(autouse=True)
def restore_registry():
    """Phase 1 SectionRegistry snapshot/restore — 4 테스트 파일 중복 DRY."""
    snapshot = dict(registry._sections)  # noqa: SLF001 — test fixture 한정
    try:
        yield
    finally:
        registry._sections.clear()  # noqa: SLF001
        registry._sections.update(snapshot)  # noqa: SLF001
```

**수정 후**:

```python
"""Pytest 공통 fixtures — registry / metrics / attachment_registry 격리 (Phase 1+2+3 패턴)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.registry import registry


@pytest.fixture(autouse=True)
def restore_registry():
    """Phase 1 SectionRegistry snapshot/restore — 4 테스트 파일 중복 DRY."""
    snapshot = dict(registry._sections)  # noqa: SLF001 — test fixture 한정
    try:
        yield
    finally:
        registry._sections.clear()  # noqa: SLF001
        registry._sections.update(snapshot)  # noqa: SLF001


@pytest.fixture(autouse=True)
def restore_attachment_registry():
    """Phase 3 AttachmentRegistry snapshot/restore — 테스트 격리."""
    snapshot = dict(attachment_registry._attachments)  # noqa: SLF001
    try:
        yield
    finally:
        attachment_registry._attachments.clear()  # noqa: SLF001
        attachment_registry._attachments.update(snapshot)  # noqa: SLF001
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_registry.py -v && uv run pytest tests/test_prompts_registry.py -v`
Expected: PASS — 3/3 신규 + Phase 1 회귀 유지

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/registry.py tests/conftest.py tests/test_attachments_registry.py
git commit -m "feat(attachments): AttachmentRegistry singleton + conftest snapshot fixture (FR-5 Task 3)"
```

---

### Task 4: RenderContext 슬롯 5개 추가 (Phase 1 backward compat)

**Files:**
- Modify: `best_agent_base/prompts/render.py:18-21`
- Test: `tests/test_attachments_ctx_slots.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_ctx_slots.py
"""RenderContext 신규 슬롯 5개 — 디폴트 값 검증 + Phase 1/2 backward compat (R-6)."""

from __future__ import annotations

from datetime import date

from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext


def test_default_constructor_no_args():
    """인자 0개 호출 가능 (Phase 1/2 회귀 방지)."""
    ctx = RenderContext()
    assert ctx.messages == ()
    assert ctx.todos == ()
    assert ctx.tool_pool == frozenset()
    assert ctx.last_emit_date is None
    assert ctx.is_subagent is False


def test_messages_slot_accepts_tuple():
    msg = Message(role="user", content=(TextBlock(text="hi"),))
    ctx = RenderContext(messages=(msg,))
    assert len(ctx.messages) == 1
    assert ctx.messages[0].role == "user"


def test_tool_pool_frozenset():
    ctx = RenderContext(tool_pool=frozenset({"Read", "Edit"}))
    assert "Read" in ctx.tool_pool


def test_last_emit_date_optional():
    ctx = RenderContext(last_emit_date=date(2026, 5, 10))
    assert ctx.last_emit_date == date(2026, 5, 10)


def test_is_subagent_boolean():
    ctx = RenderContext(is_subagent=True)
    assert ctx.is_subagent is True


def test_frozen_after_construction():
    import pytest
    from pydantic import ValidationError

    ctx = RenderContext()
    with pytest.raises(ValidationError):
        ctx.is_subagent = True  # type: ignore[misc]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_ctx_slots.py -v`
Expected: FAIL — `AttributeError: 'RenderContext' object has no attribute 'messages'`

- [ ] **Step 3: render.py 의 RenderContext 수정**

**원본** (`best_agent_base/prompts/render.py:18-21`):

```python
class RenderContext(BaseModel):
    """베이스는 빈 모델. 도메인/Phase 가 필드 추가."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
```

**수정 후**:

```python
class RenderContext(BaseModel):
    """베이스는 도메인/Phase 가 필드 추가하는 슬롯.

    Phase 3 어태치먼트 슬롯 5개 추가 — 모두 디폴트 값 보유 (R-6 backward compat):
    - messages: 대화 기록 (어태치먼트가 카운터 / smoosh 시 읽음)
    - todos: TodoWrite 도구 (Phase 5+ OOS) 슬롯, todo_reminder 가 len() 만 봄 (D6)
    - tool_pool: 현재 등록된 도구 이름 집합 (도구 풀 게이트 평가용, FR-9)
    - last_emit_date: date_change 어태치먼트 자정 감지용
    - is_subagent: True 시 MAIN_THREAD 그룹 자동 제외 (원칙 #7)
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    messages: tuple = ()  # tuple[Message, ...] — Message import 시 순환 회피
    todos: tuple = ()  # tuple[Any, ...] — D6 (Phase 5+ 형식 미정 슬롯)
    tool_pool: frozenset[str] = frozenset()
    last_emit_date: date | None = None
    is_subagent: bool = False
```

추가 import (파일 상단):

```python
from datetime import date
```

- [ ] **Step 4: 테스트 통과 확인 + Phase 1/2 회귀**

Run: `uv run pytest tests/test_attachments_ctx_slots.py tests/test_prompts_render.py tests/test_prompts_static_stability.py tests/test_cache_key_stability.py -v`
Expected: PASS — 신규 6 + Phase 1/2 모두 GREEN (backward compat 검증)

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/prompts/render.py tests/test_attachments_ctx_slots.py
git commit -m "feat(prompts): RenderContext 어태치먼트 슬롯 5개 (Task 4, R-6 backward compat)"
```

---

### Task 5: collect_attachments — 3그룹 병렬 + null 필터 + system-reminder wrap + 분기

**Files:**
- Create: `best_agent_base/attachments/collect.py`
- Test: `tests/test_attachments_collect.py`, `tests/test_attachments_collect_timeout.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성 (collect 핵심)**

```python
# tests/test_attachments_collect.py
"""collect_attachments — 3그룹 병렬 + null 필터 + wrap + 분기 (FR-3, FR-4, AC-2, AC-3)."""

from __future__ import annotations

from typing import Any

import pytest

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _Fake:
    def __init__(self, name: str, group: AttachmentGroup, output: str | None):
        self.name = name
        self.group = group
        self._output = output
        self.call_count = 0

    async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
        self.call_count += 1
        return self._output


@pytest.mark.asyncio
async def test_collect_wraps_each_in_system_reminder():
    a = _Fake("a", AttachmentGroup.ALL_THREAD, "hello")
    attachment_registry.register("a", a)
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    assert len(msgs) == 1
    text = msgs[0].content[0].text  # type: ignore[union-attr]
    assert text.startswith("<system-reminder>\n")
    assert text.endswith("\n</system-reminder>")
    assert "hello" in text


@pytest.mark.asyncio
async def test_collect_skips_none_results():
    a = _Fake("a", AttachmentGroup.ALL_THREAD, None)
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "ok")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    assert len(msgs) == 1


@pytest.mark.asyncio
async def test_user_input_none_skips_user_input_group():
    a = _Fake("a", AttachmentGroup.USER_INPUT, "skipped")
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "kept")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    msgs = await collect_attachments(RenderContext(), user_input=None)
    assert a.call_count == 0  # USER_INPUT 호출 안 됨
    assert b.call_count == 1
    assert len(msgs) == 1


@pytest.mark.asyncio
async def test_is_subagent_skips_main_thread_group():
    a = _Fake("a", AttachmentGroup.MAIN_THREAD, "skipped")
    b = _Fake("b", AttachmentGroup.ALL_THREAD, "kept")
    attachment_registry.register("a", a)
    attachment_registry.register("b", b)
    msgs = await collect_attachments(
        RenderContext(is_subagent=True), user_input="hi"
    )
    assert a.call_count == 0
    assert b.call_count == 1


@pytest.mark.asyncio
async def test_user_input_str_calls_all_three_groups():
    calls: dict[str, int] = {}
    for group_name in ["USER_INPUT", "ALL_THREAD", "MAIN_THREAD"]:
        att = _Fake(group_name.lower(), AttachmentGroup[group_name], "x")
        attachment_registry.register(group_name.lower(), att)
        calls[group_name] = att.call_count  # placeholder
    await collect_attachments(RenderContext(), user_input="hi")
    for name in ["user_input", "all_thread", "main_thread"]:
        assert attachment_registry.get(name).call_count == 1  # type: ignore[attr-defined]
```

```python
# tests/test_attachments_collect_timeout.py
"""collect_attachments 1초 타임아웃 + null 필터 (NFR-3, AC-11, R-7)."""

from __future__ import annotations

import asyncio
import time

import pytest

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _Slow:
    name = "slow"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        await asyncio.sleep(2.0)
        return "should never appear"


class _Fast:
    name = "fast"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        return "fast result"


@pytest.mark.asyncio
async def test_timeout_drops_slow_keeps_fast():
    attachment_registry.register("slow", _Slow())
    attachment_registry.register("fast", _Fast())
    started = time.monotonic()
    msgs = await collect_attachments(RenderContext(), user_input="hi")
    elapsed = time.monotonic() - started
    assert elapsed < 1.5  # 1초 + 약간의 마진
    assert any("fast result" in m.content[0].text for m in msgs)  # type: ignore[union-attr]
    assert not any("should never appear" in m.content[0].text for m in msgs)  # type: ignore[union-attr]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_collect.py tests/test_attachments_collect_timeout.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: collect.py 구현**

```python
# best_agent_base/attachments/collect.py
"""collect_attachments — 3그룹 병렬 + null 필터 + system-reminder wrap (FR-3, FR-4).

D4: <system-reminder> wrap 은 베이스 책임.
D5: 단일 함수 + user_input=None 분기.
D9: asyncio.wait_for(gather, timeout=1.0) + 개별 try/except → None.
D10: ctx.is_subagent=True 시 MAIN_THREAD 자동 제외.

CC `messages.ts:3098` wrap 형식 그대로.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from best_agent_base.attachments.gates import is_gated
from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext

COLLECT_TIMEOUT_SECONDS = 1.0


def _wrap_system_reminder(text: str) -> str:
    """CC messages.ts:3098 형식 그대로."""
    return f"<system-reminder>\n{text}\n</system-reminder>"


def _select_groups(*, user_input: str | None, is_subagent: bool) -> list[AttachmentGroup]:
    groups: list[AttachmentGroup] = []
    if user_input is not None:
        groups.append(AttachmentGroup.USER_INPUT)
    groups.append(AttachmentGroup.ALL_THREAD)
    if not is_subagent:
        groups.append(AttachmentGroup.MAIN_THREAD)
    return groups


async def _safe_build(att: Attachment, ctx: RenderContext) -> str | None:
    """개별 어태치먼트 build() 실패는 None 으로 흡수 (NFR-3 / R-7)."""
    try:
        return await att.build(ctx)
    except Exception:
        return None


def _attachments_in(groups: Iterable[AttachmentGroup], tool_pool: frozenset[str]) -> list[Attachment]:
    """그룹별 어태치먼트 + 도구 풀 게이트 통과한 것만 반환 (FR-9)."""
    out: list[Attachment] = []
    for g in groups:
        for att in attachment_registry.all_in_group(g):
            if not is_gated(att.name, tool_pool):
                out.append(att)
    return out


async def collect_attachments(
    ctx: RenderContext,
    *,
    user_input: str | None,
) -> list[Message]:
    """3그룹 어태치먼트 병렬 수집 + null 필터 + system-reminder wrap.

    user_input=str  → USER_INPUT + ALL_THREAD + MAIN_THREAD 모두 호출 (user-turn entry)
    user_input=None → ALL_THREAD + MAIN_THREAD 만 호출 (in-loop, 도구 라운드 후)
    is_subagent=True → MAIN_THREAD 그룹 자동 제외 (원칙 #7)

    각 결과 → Message(role="user", content=(TextBlock(<system-reminder>...),))
    """
    groups = _select_groups(user_input=user_input, is_subagent=ctx.is_subagent)
    targets = _attachments_in(groups, ctx.tool_pool)
    if not targets:
        return []

    coros = [_safe_build(att, ctx) for att in targets]
    try:
        results = await asyncio.wait_for(asyncio.gather(*coros), timeout=COLLECT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        # 전체 타임아웃 — 부분 결과 회수 불가, 빈 결과 반환
        return []

    return [
        Message(role="user", content=(TextBlock(text=_wrap_system_reminder(r)),))
        for r in results
        if r is not None
    ]
```

`gates.py` 가 아직 없어서 import 실패 — Task 9 에서 채움. **임시 스텁** 으로 진행:

```python
# best_agent_base/attachments/gates.py — 임시 스텁 (Task 9 에서 본 구현)
"""도구 풀 인지 게이트 — 임시 스텁 (Task 9 본 구현)."""

from __future__ import annotations


def is_gated(attachment_name: str, tool_pool: frozenset[str]) -> bool:  # noqa: ARG001
    return False
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_collect.py tests/test_attachments_collect_timeout.py -v`
Expected: PASS — 5 + 1 = 6/6 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/collect.py best_agent_base/attachments/gates.py tests/test_attachments_collect.py tests/test_attachments_collect_timeout.py
git commit -m "feat(attachments): collect_attachments 3그룹 병렬 + null + wrap + 분기 + gates 스텁 (FR-3/4 Task 5)"
```

---

### Task 6: count_turns_since 헬퍼

**Files:**
- Create: `best_agent_base/attachments/counter.py`
- Test: `tests/test_attachments_counter.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_counter.py
"""count_turns_since — assistant turn 카운터, thinking 제외 (FR-6, AC-5, R-8)."""

from __future__ import annotations

from best_agent_base.attachments.counter import count_turns_since
from best_agent_base.messages import Message, TextBlock, ThinkingBlock, ToolUseBlock


def _user(text: str) -> Message:
    return Message(role="user", content=(TextBlock(text=text),))


def _assistant_text(text: str) -> Message:
    return Message(role="assistant", content=(TextBlock(text=text),))


def _assistant_thinking_only(text: str) -> Message:
    return Message(role="assistant", content=(ThinkingBlock(text=text),))


def _assistant_tool_use(name: str) -> Message:
    return Message(
        role="assistant",
        content=(ToolUseBlock(id="x", name=name, input={}),),
    )


def test_count_until_predicate_match():
    msgs = (
        _assistant_text("a"),
        _assistant_text("b"),
        _assistant_tool_use("TodoWrite"),  # match
        _assistant_text("c"),
        _assistant_text("d"),
    )
    n = count_turns_since(
        msgs, lambda m: m.role == "assistant" and any(
            getattr(b, "name", None) == "TodoWrite" for b in m.content
        )
    )
    assert n == 2  # c, d


def test_thinking_only_messages_excluded_from_count():
    msgs = (
        _assistant_tool_use("TodoWrite"),
        _assistant_thinking_only("reason"),
        _assistant_text("real"),
        _assistant_thinking_only("reason2"),
    )
    n = count_turns_since(
        msgs, lambda m: any(getattr(b, "name", None) == "TodoWrite" for b in m.content)
    )
    assert n == 1  # "real" only — thinking-only 2개는 카운트 안 함


def test_no_match_returns_total_assistant_count():
    msgs = (_user("hi"), _assistant_text("a"), _assistant_text("b"))
    n = count_turns_since(msgs, lambda m: False)
    assert n == 2


def test_empty_messages_returns_zero():
    assert count_turns_since((), lambda m: True) == 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_counter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
# best_agent_base/attachments/counter.py
"""assistant turn 카운터 (FR-6).

CC `attachments.ts:3215~3263` 거울 — 비-thinking assistant 메시지만 카운트.
predicate 만족 메시지 발견 시 종료, 없으면 전체 카운트 반환.
"""

from __future__ import annotations

from collections.abc import Callable

from best_agent_base.messages import Message


def _is_thinking_only(msg: Message) -> bool:
    return all(b.type == "thinking" for b in msg.content)


def count_turns_since(
    messages: tuple[Message, ...],
    predicate: Callable[[Message], bool],
) -> int:
    """messages 끝부터 거꾸로 훑으면서 비-thinking assistant 카운트.

    predicate(msg)=True 만나면 종료, 못 만나면 전체 비-thinking assistant 수.
    thinking-only assistant 메시지는 카운트에서 제외 (R-8).
    """
    count = 0
    for msg in reversed(messages):
        if msg.role != "assistant":
            continue
        if _is_thinking_only(msg):
            continue
        if predicate(msg):
            return count
        count += 1
    return count
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_counter.py -v`
Expected: PASS — 4/4 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/counter.py tests/test_attachments_counter.py
git commit -m "feat(attachments): count_turns_since 헬퍼 (FR-6 Task 6)"
```

---

### Task 7: smoosh_into_last_tool_result 헬퍼

**Files:**
- Create: `best_agent_base/attachments/smoosh.py`
- Test: `tests/test_attachments_smoosh.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_smoosh.py
"""smoosh_into_last_tool_result — in-loop 결과 + reminder 합성 (FR-7, AC-6, R-5)."""

from __future__ import annotations

from best_agent_base.attachments.smoosh import smoosh_into_last_tool_result
from best_agent_base.messages import Message, TextBlock, ToolResultBlock


def _user_with_tool_result(tool_use_id: str, content: str) -> Message:
    return Message(
        role="user",
        content=(ToolResultBlock(tool_use_id=tool_use_id, content=content),),
    )


def _user_text(text: str) -> Message:
    return Message(role="user", content=(TextBlock(text=text),))


def test_smoosh_appends_text_block_to_last_user_message():
    msgs = (_user_with_tool_result("toolu_1", "result A"),)
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out) == 1
    last = out[-1]
    assert len(last.content) == 2
    assert isinstance(last.content[0], ToolResultBlock)
    assert last.content[0].tool_use_id == "toolu_1"  # 보존
    assert isinstance(last.content[1], TextBlock)
    assert last.content[1].text == "<system-reminder>x</system-reminder>"


def test_no_tool_result_appends_separate_user_message():
    msgs = (_user_text("hi"),)
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out) == 2
    assert out[1].role == "user"
    assert isinstance(out[1].content[0], TextBlock)


def test_multiple_tool_results_only_last_user_msg_smooshed():
    msgs = (
        _user_with_tool_result("toolu_1", "A"),
        _user_with_tool_result("toolu_2", "B"),
    )
    out = smoosh_into_last_tool_result(msgs, "<system-reminder>x</system-reminder>")
    assert len(out[0].content) == 1  # 첫 user 변경 없음
    assert len(out[1].content) == 2  # 마지막 user 에만 reminder 합성


def test_empty_messages_returns_separate_user_message():
    out = smoosh_into_last_tool_result((), "<system-reminder>x</system-reminder>")
    assert len(out) == 1
    assert out[0].role == "user"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_smoosh.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
# best_agent_base/attachments/smoosh.py
"""smoosh_into_last_tool_result — in-loop 결과 + reminder 합성 (FR-7).

CC `messages.ts:1835` 거울 — 마지막 user 메시지의 마지막 tool_result 옆에
reminder text 블록 append. provider strict alternation 대응 (Gemini/Anthropic 호환).
tool_call_id 보존 — content tuple 그대로 두고 끝에 TextBlock 만 추가.
"""

from __future__ import annotations

from best_agent_base.messages import Message, TextBlock, ToolResultBlock


def _has_tool_result(msg: Message) -> bool:
    return any(isinstance(b, ToolResultBlock) for b in msg.content)


def smoosh_into_last_tool_result(
    messages: tuple[Message, ...],
    reminder_text: str,
) -> tuple[Message, ...]:
    """마지막 user 메시지가 tool_result 가지면 같은 메시지에 TextBlock append.

    없으면 별도 user 메시지로 추가. tool_call_id 는 ToolResultBlock 객체
    그대로 보존됨 (frozen, 새 메시지로 재구성).
    """
    if messages and messages[-1].role == "user" and _has_tool_result(messages[-1]):
        last = messages[-1]
        new_content = last.content + (TextBlock(text=reminder_text),)
        new_last = Message(role="user", content=new_content)
        return messages[:-1] + (new_last,)

    extra = Message(role="user", content=(TextBlock(text=reminder_text),))
    return messages + (extra,)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_smoosh.py -v`
Expected: PASS — 4/4 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/smoosh.py tests/test_attachments_smoosh.py
git commit -m "feat(attachments): smoosh_into_last_tool_result 헬퍼 (FR-7 Task 7)"
```

---

### Task 8: register_tool_pool_gate + OR 평가 (gates.py 본 구현)

**Files:**
- Modify: `best_agent_base/attachments/gates.py` (Task 5 의 임시 스텁 → 본 구현)
- Test: `tests/test_attachments_gates.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_gates.py
"""register_tool_pool_gate — predicate 등록 + OR 평가 (FR-9, AC-8, D7)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.gates import (
    _gates,  # noqa: SLF001 — 테스트에서 격리용
    is_gated,
    register_tool_pool_gate,
)


@pytest.fixture(autouse=True)
def _reset_gates():
    snapshot = {k: list(v) for k, v in _gates.items()}
    yield
    _gates.clear()
    _gates.update(snapshot)


def test_no_gate_registered_returns_false():
    assert is_gated("foo", frozenset({"Read"})) is False


def test_single_gate_true_means_gated():
    register_tool_pool_gate("todo_reminder", lambda tools: "SendUserMessage" in tools)
    assert is_gated("todo_reminder", frozenset({"SendUserMessage", "Read"})) is True
    assert is_gated("todo_reminder", frozenset({"Read"})) is False


def test_multiple_gates_or_evaluation():
    """어태치먼트당 N개 게이트, true 1개 만나면 스킵 (D7)."""
    register_tool_pool_gate("att", lambda tools: "X" in tools)
    register_tool_pool_gate("att", lambda tools: "Y" in tools)
    assert is_gated("att", frozenset({"X"})) is True  # 첫 게이트 true
    assert is_gated("att", frozenset({"Y"})) is True  # 둘째 게이트 true
    assert is_gated("att", frozenset({"X", "Y"})) is True
    assert is_gated("att", frozenset({"Z"})) is False  # 둘 다 false
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_gates.py -v`
Expected: FAIL — `is_gated` 가 항상 False (Task 5 의 스텁) → 일부 케이스 실패

- [ ] **Step 3: 본 구현으로 교체**

**원본** (`best_agent_base/attachments/gates.py`):

```python
"""도구 풀 인지 게이트 — 임시 스텁 (Task 9 본 구현)."""

from __future__ import annotations


def is_gated(attachment_name: str, tool_pool: frozenset[str]) -> bool:  # noqa: ARG001
    return False
```

**수정 후**:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인 + Task 5 회귀**

Run: `uv run pytest tests/test_attachments_gates.py tests/test_attachments_collect.py -v`
Expected: PASS — 4/4 신규 + Task 5 collect 5/5 회귀 GREEN

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/gates.py tests/test_attachments_gates.py
git commit -m "feat(attachments): register_tool_pool_gate + OR 평가 본 구현 (FR-9 Task 8)"
```

---

### Task 9: 베이스 디폴트 어태치먼트 — date_change

**Files:**
- Create: `best_agent_base/attachments/builtins/__init__.py`
- Create: `best_agent_base/attachments/builtins/date_change.py`
- Test: `tests/test_attachments_builtins_date.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_builtins_date.py
"""date_change 어태치먼트 — 자정 감지 (FR-8, AC-7)."""

from __future__ import annotations

from datetime import date

import pytest

from best_agent_base.attachments.builtins.date_change import date_change_attachment
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.prompts.render import RenderContext


def test_metadata():
    assert date_change_attachment.name == "date_change"
    assert date_change_attachment.group == AttachmentGroup.ALL_THREAD


@pytest.mark.asyncio
async def test_first_call_no_last_emit_skips():
    """last_emit_date None → 베이스라인 잡기, 발화 안 함."""
    ctx = RenderContext(last_emit_date=None)
    out = await date_change_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_same_day_skips():
    ctx = RenderContext(last_emit_date=date.today())
    out = await date_change_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_yesterday_emits_with_today_date():
    from datetime import timedelta

    yesterday = date.today() - timedelta(days=1)
    ctx = RenderContext(last_emit_date=yesterday)
    out = await date_change_attachment.build(ctx)
    assert out is not None
    assert "date has changed" in out.lower() or "날짜" in out
    assert str(date.today()) in out
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_builtins_date.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
# best_agent_base/attachments/builtins/__init__.py
"""베이스 디폴트 어태치먼트 — date_change + todo_reminder (FR-8).

D-13: docstring-only. 객체는 서브모듈에서 import.
모듈 import 시 attachment_registry 에 자동 등록 (Phase 1 SectionRegistry 패턴 거울).
"""
```

```python
# best_agent_base/attachments/builtins/date_change.py
"""date_change — OS 시계 기반 자정 감지 어태치먼트 (FR-8, ALL_THREAD)."""

from __future__ import annotations

from datetime import date

from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.prompts.render import RenderContext


class _DateChange:
    name = "date_change"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:
        last = ctx.last_emit_date
        today = date.today()
        if last is None:
            return None  # 베이스라인 — 첫 호출 시 발화 안 함
        if last == today:
            return None
        return (
            f"The date has changed. Today's date is now {today.isoformat()}. "
            "DO NOT mention this to the user explicitly because they are already aware."
        )


date_change_attachment = _DateChange()
attachment_registry.register("date_change", date_change_attachment)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_builtins_date.py -v`
Expected: PASS — 4/4 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/builtins/__init__.py best_agent_base/attachments/builtins/date_change.py tests/test_attachments_builtins_date.py
git commit -m "feat(attachments): date_change 베이스 디폴트 어태치먼트 (FR-8 Task 9)"
```

---

### Task 10: 베이스 디폴트 어태치먼트 — todo_reminder (counter + gate 통합)

**Files:**
- Create: `best_agent_base/attachments/builtins/todo_reminder.py`
- Test: `tests/test_attachments_builtins_todo.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_builtins_todo.py
"""todo_reminder — 10 round 게이트 + counter + tool pool gate 통합 (FR-8 + FR-9 통합 시연)."""

from __future__ import annotations

import pytest

from best_agent_base.attachments.builtins.todo_reminder import (
    TODO_REMINDER_THRESHOLD,
    todo_reminder_attachment,
)
from best_agent_base.attachments.gates import _gates, register_tool_pool_gate
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext


def _assistant_tool(name: str) -> Message:
    return Message(
        role="assistant",
        content=(ToolUseBlock(id="x", name=name, input={}),),
    )


def _assistant_text(text: str) -> Message:
    return Message(role="assistant", content=(TextBlock(text=text),))


@pytest.fixture(autouse=True)
def _reset_gates():
    snapshot = {k: list(v) for k, v in _gates.items()}
    yield
    _gates.clear()
    _gates.update(snapshot)


def test_metadata():
    assert todo_reminder_attachment.name == "todo_reminder"
    assert todo_reminder_attachment.group == AttachmentGroup.ALL_THREAD
    assert TODO_REMINDER_THRESHOLD == 10


@pytest.mark.asyncio
async def test_under_threshold_skips():
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD - 1))
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is None


@pytest.mark.asyncio
async def test_at_threshold_emits():
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD))
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is not None
    assert "todo" in out.lower()


@pytest.mark.asyncio
async def test_recent_todowrite_resets_counter_skips():
    msgs = (
        _assistant_tool("TodoWrite"),
        _assistant_text("r1"),
        _assistant_text("r2"),
    )
    ctx = RenderContext(messages=msgs)
    out = await todo_reminder_attachment.build(ctx)
    assert out is None  # TodoWrite 직후 = 0 카운트 + 2 → 임계 미만


@pytest.mark.asyncio
async def test_external_gate_skips_when_tool_in_pool():
    register_tool_pool_gate("todo_reminder", lambda tools: "GateTool" in tools)
    msgs = tuple(_assistant_text(f"r{i}") for i in range(TODO_REMINDER_THRESHOLD))
    ctx = RenderContext(messages=msgs, tool_pool=frozenset({"GateTool"}))
    # gate 는 collect_attachments 에서 평가됨 — 어태치먼트 자체 build() 는 트리거됨
    # 본 테스트는 build() 단독 호출이라 게이트 우회됨 → 발화. 통합 테스트는 Task 15 에서.
    out = await todo_reminder_attachment.build(ctx)
    assert out is not None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_builtins_todo.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
# best_agent_base/attachments/builtins/todo_reminder.py
"""todo_reminder — 10 round 게이트 + counter + 자동 등록 (FR-8, ALL_THREAD).

CC `attachments.ts:254~257` 임계값 거울 (TURNS_SINCE_WRITE=10).
ctx.todos 본문은 박지 않음 (D6 — Phase 5+ 형식 미정 슬롯) — len() 만 본문에 포함.
"""

from __future__ import annotations

from best_agent_base.attachments.counter import count_turns_since
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message
from best_agent_base.prompts.render import RenderContext

TODO_REMINDER_THRESHOLD = 10


def _has_tool_use_named(msg: Message, name: str) -> bool:
    return any(getattr(b, "name", None) == name for b in msg.content)


class _TodoReminder:
    name = "todo_reminder"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:
        turns = count_turns_since(
            ctx.messages,
            lambda m: m.role == "assistant" and _has_tool_use_named(m, "TodoWrite"),
        )
        if turns < TODO_REMINDER_THRESHOLD:
            return None
        return (
            "The TodoWrite tool hasn't been used recently. If you're working on tasks "
            "that would benefit from tracking progress, consider using TodoWrite to "
            "track progress. Also consider cleaning up the todo list if it has become "
            "stale and no longer matches what you are working on. Only use it if it's "
            "relevant to the current work. This is just a gentle reminder — ignore if "
            "not applicable. Make sure that you NEVER mention this reminder to the user.\n\n"
            f"Current todo count: {len(ctx.todos)}"
        )


todo_reminder_attachment = _TodoReminder()
attachment_registry.register("todo_reminder", todo_reminder_attachment)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_builtins_todo.py -v`
Expected: PASS — 5/5 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/builtins/todo_reminder.py tests/test_attachments_builtins_todo.py
git commit -m "feat(attachments): todo_reminder 베이스 디폴트 + counter + gate 통합 (FR-8 Task 10)"
```

---

### Task 11: call_with_attachments helper β (Phase 2 LLMClient 통합)

**Files:**
- Create: `best_agent_base/attachments/integrate.py`
- Test: `tests/test_attachments_helper_integration.py`

**Model**: sonnet

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_attachments_helper_integration.py
"""call_with_attachments helper β — Phase 2 LLMClient 통합 (D3, FR-3 + FR-4 통합)."""

from __future__ import annotations

from typing import Any

import pytest

from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


class _MockClient:
    def __init__(self) -> None:
        self.calls: list[tuple[RenderContext, CachePolicy | None]] = []

    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        self.calls.append((ctx, cache_policy))
        return LLMResponse(
            text="ok",
            static_hash="abc123",
            cache_hit=False,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    def count_tokens(self, text: str) -> int:
        return len(text.split())


class _Fake:
    name = "fake"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx: RenderContext) -> str | None:  # noqa: ARG002
        return "attachment-data"


@pytest.mark.asyncio
async def test_helper_calls_collect_then_generate():
    attachment_registry.register("fake", _Fake())
    client = _MockClient()
    ctx = RenderContext()

    response = await call_with_attachments(client, ctx, user_input="hi")

    assert response.text == "ok"
    assert len(client.calls) == 1
    new_ctx, _ = client.calls[0]
    # ctx.messages 에 user_input + 어태치먼트 메시지 합성 검증
    texts = [b.text for m in new_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("hi" == t for t in texts)
    assert any("attachment-data" in t for t in texts)


@pytest.mark.asyncio
async def test_helper_passes_cache_policy_through():
    client = _MockClient()
    policy = CachePolicy(enabled=False)

    await call_with_attachments(client, RenderContext(), user_input="x", cache_policy=policy)

    _, passed_policy = client.calls[0]
    assert passed_policy is policy


@pytest.mark.asyncio
async def test_helper_preserves_existing_messages():
    from best_agent_base.messages import Message, TextBlock

    prior = (Message(role="user", content=(TextBlock(text="prior"),)),)
    client = _MockClient()

    await call_with_attachments(client, RenderContext(messages=prior), user_input="new")

    new_ctx, _ = client.calls[0]
    # prior + new user_input + (어태치먼트 0개)
    assert new_ctx.messages[0].content[0].text == "prior"  # type: ignore[union-attr]
    assert new_ctx.messages[1].content[0].text == "new"  # type: ignore[union-attr]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_helper_integration.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

```python
# best_agent_base/attachments/integrate.py
"""call_with_attachments helper β (D3) — Phase 2 LLMClient 통합.

flow: collect_attachments → ctx.messages 합성 (기존 + user_input + 어태치먼트) → client.generate(new_ctx)

Phase 2 LLMClient.generate(ctx, *, cache_policy) 시그니처 무변경 보존 (B-thin).
ReAct 루프 (Phase 5+) 가 본격 통합 시 본 helper 흡수.
"""

from __future__ import annotations

from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.llm.cache_policy import CachePolicy
from best_agent_base.llm.client import LLMClient, LLMResponse
from best_agent_base.messages import Message, TextBlock
from best_agent_base.prompts.render import RenderContext


async def call_with_attachments(
    client: LLMClient,
    ctx: RenderContext,
    *,
    user_input: str,
    cache_policy: CachePolicy | None = None,
) -> LLMResponse:
    """user-turn entry helper. 어태치먼트 수집 + ctx.messages 합성 + LLM 호출.

    NFR-2 정적 캐시 안전 자동 보장 — 어태치먼트는 무조건 ctx.messages 에만 적재,
    Phase 1 BOUNDARY 위 정적 7섹션은 안 건드림.
    """
    attachment_messages = await collect_attachments(ctx, user_input=user_input)
    user_msg = Message(role="user", content=(TextBlock(text=user_input),))
    new_messages = ctx.messages + (user_msg,) + tuple(attachment_messages)
    new_ctx = ctx.model_copy(update={"messages": new_messages})
    return await client.generate(new_ctx, cache_policy=cache_policy)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_attachments_helper_integration.py -v`
Expected: PASS — 3/3 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/attachments/integrate.py tests/test_attachments_helper_integration.py
git commit -m "feat(attachments): call_with_attachments helper β (D3 Phase 2 통합 Task 11)"
```

---

### Task 12: NFR-1 도메인 중립성 grep 확장

**Files:**
- Modify: `tests/test_no_domain_vocab.py:14-17`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성 (= grep 확장 자체)**

**원본** (`tests/test_no_domain_vocab.py:13-72`):

```python
PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "best_agent_base" / "prompts"
LLM_DIR = PROJECT_ROOT / "best_agent_base" / "llm"

SCAN_DIRS: tuple[Path, ...] = (PROMPTS_DIR, LLM_DIR)

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


def test_prompts_dir_exists():
    """디렉토리 자체가 존재해야 검증이 의미 있음."""
    assert PROMPTS_DIR.is_dir()


def test_llm_dir_exists():
    """디렉토리 자체가 존재해야 검증이 의미 있음."""
    assert LLM_DIR.is_dir()
```

**수정 후**:

```python
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
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/test_no_domain_vocab.py -v`
Expected: PASS — 모든 도메인 키워드 attachments/ + messages.py 안에 0건

- [ ] **Step 3: (구현 없음 — 테스트 = 검증)**

스킵.

- [ ] **Step 4: 통과 확인**

(Step 2 와 동일)

- [ ] **Step 5: 커밋**

```bash
git add tests/test_no_domain_vocab.py
git commit -m "test(no-domain-vocab): attachments/ + messages.py 까지 grep 범위 확장 (NFR-1 Task 12)"
```

---

### Task 13: NFR-2 정적 캐시 안전 invariant 회귀

**Files:**
- Test: `tests/test_attachments_static_hash_invariant.py`

**Model**: haiku

- [ ] **Step 1: 테스트 작성 (검증 전용 — 구현 없음)**

```python
# tests/test_attachments_static_hash_invariant.py
"""NFR-2 정적 캐시 안전 invariant — 어태치먼트 발화 전후 get_static_hash 동일 (AC-10, R-4)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from best_agent_base.attachments.builtins import date_change as _dc  # auto-register
from best_agent_base.attachments.builtins import todo_reminder as _tr  # auto-register
from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.protocol import AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext, get_static_hash

# import 만 해서 lint warning 회피
_ = (_dc, _tr)


class _Loud:
    name = "loud"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx):  # noqa: ARG002
        return "noisy attachment text " * 50  # 충분히 긴 텍스트


def test_static_hash_unchanged_by_attachment_registration():
    hash_before = get_static_hash(RenderContext())
    attachment_registry.register("loud", _Loud())
    hash_after = get_static_hash(RenderContext())
    assert hash_before == hash_after, "어태치먼트 등록만으로 정적 해시 변동 X (NFR-2)"


@pytest.mark.asyncio
async def test_static_hash_unchanged_by_attachment_emit():
    attachment_registry.register("loud", _Loud())
    yesterday = date.today() - timedelta(days=1)
    msgs = (
        Message(role="assistant", content=(ToolUseBlock(id="x", name="X", input={}),)),
    )
    ctx = RenderContext(
        messages=msgs * 12,  # todo_reminder 트리거
        last_emit_date=yesterday,  # date_change 트리거
        todos=("a", "b"),
    )
    hash_before = get_static_hash(ctx)
    msgs_out = await collect_attachments(ctx, user_input="hi")
    assert len(msgs_out) >= 1  # 어태치먼트 발화 확인
    hash_after = get_static_hash(ctx)
    assert hash_before == hash_after, "어태치먼트 발화 후도 정적 해시 변동 X"


def test_dynamic_part_does_not_leak_into_static():
    """RenderContext 슬롯에 데이터 넣어도 정적 해시 불변."""
    hash_empty = get_static_hash(RenderContext())
    hash_with_messages = get_static_hash(
        RenderContext(messages=(Message(role="user", content=(TextBlock(text="x"),)),))
    )
    hash_with_pool = get_static_hash(RenderContext(tool_pool=frozenset({"a", "b"})))
    assert hash_empty == hash_with_messages == hash_with_pool
```

- [ ] **Step 2: 테스트 실행 (= invariant 회귀 검증)**

Run: `uv run pytest tests/test_attachments_static_hash_invariant.py -v`
Expected: PASS — 3/3 tests (Phase 1 BOUNDARY + Phase 3 ctx 슬롯 = 정적부 무변경)

- [ ] **Step 3: (구현 없음 — invariant 검증 전용)**

스킵.

- [ ] **Step 4: 통과 확인**

(Step 2 동일)

- [ ] **Step 5: 커밋**

```bash
git add tests/test_attachments_static_hash_invariant.py
git commit -m "test(attachments): NFR-2 정적 캐시 안전 invariant 회귀 (R-4 Task 13)"
```

---

### Task 14: NFR-4 init purity AST 검사

**Files:**
- Test: `tests/test_attachments_init_purity.py`

**Model**: haiku

- [ ] **Step 1: 테스트 작성**

```python
# tests/test_attachments_init_purity.py
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
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/test_attachments_init_purity.py -v`
Expected: PASS — 2/2 (Task 2 + Task 9 의 __init__.py 모두 docstring-only)

- [ ] **Step 3: (구현 없음 — invariant 검증 전용)**

스킵.

- [ ] **Step 4: 통과 확인**

(Step 2 동일)

- [ ] **Step 5: 커밋**

```bash
git add tests/test_attachments_init_purity.py
git commit -m "test(attachments): NFR-4 init purity AST 검사 (Task 14)"
```

---

### Task 15: 통합 full flow + main.py 데모 마이그레이션

**Files:**
- Modify: `main.py`
- Test: `tests/test_attachments_full_flow.py`

**Model**: sonnet

- [ ] **Step 1: 통합 테스트 작성**

```python
# tests/test_attachments_full_flow.py
"""통합 — call_with_attachments + 베이스 디폴트 어태치먼트 + mock LLMClient (시연)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from best_agent_base.attachments.builtins import date_change as _dc  # auto-register
from best_agent_base.attachments.builtins import todo_reminder as _tr  # auto-register
from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.messages import Message, TextBlock, ToolUseBlock
from best_agent_base.prompts.render import RenderContext

_ = (_dc, _tr)


class _MockClient:
    def __init__(self) -> None:
        self.last_ctx: RenderContext | None = None

    async def generate(self, ctx, *, cache_policy=None):  # noqa: ARG002
        self.last_ctx = ctx
        return LLMResponse(
            text="ok",
            static_hash="abc123",
            cache_hit=False,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
        )

    def count_tokens(self, text):
        return len(text.split())


@pytest.mark.asyncio
async def test_full_flow_date_change_emits():
    yesterday = date.today() - timedelta(days=1)
    client = _MockClient()
    ctx = RenderContext(last_emit_date=yesterday)

    await call_with_attachments(client, ctx, user_input="안녕")

    assert client.last_ctx is not None
    texts = [b.text for m in client.last_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("date has changed" in t.lower() for t in texts)


@pytest.mark.asyncio
async def test_full_flow_todo_reminder_emits_at_threshold():
    msgs = tuple(
        Message(role="assistant", content=(TextBlock(text=f"r{i}"),))
        for i in range(10)
    )
    client = _MockClient()
    ctx = RenderContext(messages=msgs)

    await call_with_attachments(client, ctx, user_input="진행해")

    texts = [b.text for m in client.last_ctx.messages for b in m.content if hasattr(b, "text")]
    assert any("TodoWrite" in t for t in texts)


@pytest.mark.asyncio
async def test_full_flow_no_attachments_when_quiet_state():
    client = _MockClient()
    ctx = RenderContext()  # 빈 ctx, last_emit_date=None, messages=()

    await call_with_attachments(client, ctx, user_input="안녕")

    # user_input 만 추가, 어태치먼트 메시지 없음
    assert len(client.last_ctx.messages) == 1
    assert client.last_ctx.messages[0].content[0].text == "안녕"  # type: ignore[union-attr]
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/test_attachments_full_flow.py -v`
Expected: PASS — 3/3 (베이스 디폴트 + helper + mock client 통합 시연)

- [ ] **Step 3: main.py 데모 마이그레이션**

**원본** (`main.py` 의 핵심 — `client.generate(RenderContext())` 단순 호출):

main.py 의 현재 코드를 Read 한 후 (이미 Phase 2 에서 GeminiClient 호출하는 형태), `call_with_attachments` 사용으로 교체.

**수정 후** (`main.py` 핵심 부분):

```python
"""Phase 0~3 데모 — call_with_attachments helper + GeminiClient (Phase 2 어댑터)."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from dotenv import load_dotenv

from best_agent_base.attachments.builtins import date_change   # auto-register  # noqa: F401
from best_agent_base.attachments.builtins import todo_reminder  # auto-register  # noqa: F401
from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def main() -> None:
    load_dotenv()
    client = GeminiClient()

    # 베이스라인 — 어태치먼트 0개 (last_emit_date None, messages 빈 튜플)
    ctx = RenderContext()
    response = await call_with_attachments(client, ctx, user_input="hello")
    print(f"[basic] {response.text}")

    # date_change 어태치먼트 활성 — yesterday 박아서 자정 감지 트리거
    yesterday = date.today() - timedelta(days=1)
    ctx_with_yesterday = RenderContext(last_emit_date=yesterday)
    response = await call_with_attachments(client, ctx_with_yesterday, user_input="hello again")
    print(f"[date_change emitted] {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: 데모 + 테스트 통과 확인**

Run:

```bash
uv run pytest tests/test_attachments_full_flow.py -v
uv run python main.py  # 환경 변수 GOOGLE_API_KEY 있으면 실제 호출, 없으면 RuntimeError
```

Expected: pytest PASS 3/3. main.py 는 환경 변수 따라 작동/에러.

- [ ] **Step 5: 커밋**

```bash
git add main.py tests/test_attachments_full_flow.py
git commit -m "feat(integration): full flow 통합 테스트 + main.py call_with_attachments 데모 (Task 15)"
```

---

### Task 16: 최종 GREEN + ruff clean + 카운트 검증

**Files:** (테스트만 — 검증 전용)

**Model**: sonnet

- [ ] **Step 1: 전체 테스트 GREEN 확인**

Run:

```bash
uv run pytest -v 2>&1 | tail -20
```

Expected: 146~161 tests, PASS, 0 fail. (Phase 1: 70, Phase 2: +41 = 111, Phase 3: +35~50 = 146~161)

- [ ] **Step 2: ruff clean 확인**

Run:

```bash
uv run ruff check best_agent_base/ tests/ main.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Phase 1/2 회귀 None 확인**

Run:

```bash
uv run pytest tests/test_prompts_render.py tests/test_prompts_static_stability.py tests/test_cache_key_stability.py tests/test_gemini_adapter.py tests/test_anthropic_adapter.py -v
```

Expected: Phase 1/2 모든 테스트 PASS (R-6 backward compat 검증)

- [ ] **Step 4: 카운트 출력**

```bash
uv run pytest --collect-only -q | tail -3
```
Expected: 출력의 마지막 줄에 총 테스트 수 (146~161 범위 내)

- [ ] **Step 5: 검증 완료 커밋 (선택 — 검증만이라 코드 변경 없음, 커밋 스킵)**

---

## 2. 위험 코드 지점

tech-design §6 R-1..R-8 → file:line + mitigation 매핑.

- `best_agent_base/attachments/registry.py:AttachmentRegistry` — **race**: register/override 동시성 (멀티-요청). Mitigation: register 1회 + read-many 가정 (Phase 1 R-1 패턴), Phase 14 ContextVar 재검토.
- `best_agent_base/attachments/collect.py:collect_attachments` — **race**: gather 안 build() 가 외부 store mutation 시 race. Mitigation: ctx frozen + read-only 가정. mutation 은 도메인 책임.
- `best_agent_base/attachments/collect.py:_wrap_system_reminder` — **side-effect**: 도메인이 build() 안 직접 wrap 시 이중 wrap. Mitigation: D4 — 베이스가 wrap 책임, Attachment.build docstring + 인터페이스 가이드 명시.
- `best_agent_base/prompts/render.py:RenderContext` — **side-effect**: 어태치먼트가 BOUNDARY 위 정적부로 새어들어감. Mitigation: `tests/test_attachments_static_hash_invariant.py` 회귀 (Task 13). helper β 가 ctx.messages 만 적재.
- `best_agent_base/attachments/smoosh.py:smoosh_into_last_tool_result` — **side-effect**: tool_call_id 누락 시 SDK 에러. Mitigation: ToolResultBlock 객체 그대로 보존 (frozen + 새 메시지 재구성), `tests/test_attachments_smoosh.py` 단위 테스트.
- `best_agent_base/prompts/render.py:RenderContext` — **breaking**: 슬롯 5개 추가가 Phase 1/2 회귀 깨뜨림 가능. Mitigation: 모든 신규 필드 디폴트 값, `tests/test_attachments_ctx_slots.py` + Phase 1/2 회귀 테스트 (Task 4 Step 4).
- `best_agent_base/attachments/collect.py:collect_attachments` — **side-effect**: 1초 타임아웃 시 long-running 어태치먼트 잘림 (NFR-3 의 의도된 trade-off). Mitigation: NFR-3 명시, 도메인이 1초 넘는 fetch 는 백그라운드 캐싱.
- `best_agent_base/attachments/counter.py:count_turns_since` — **side-effect**: thinking 메시지 식별 잘못 → todo_reminder 잘못된 시점 발화. Mitigation: `_is_thinking_only` = `all(b.type == "thinking" for b in msg.content)` 명확 정의, `tests/test_attachments_counter.py` thinking-only/혼합 케이스.

## 3. 롤백 전략

- **Code**: per-task 정책 — 각 task = 1 atomic commit. 문제 발생 task 의 commit 만 `git revert <SHA>` 또는 `git reset --hard HEAD~N`. Phase 1/2 회귀 깨지면 Task 4 (RenderContext 슬롯 추가) commit 우선 revert.
- **DB**: 변경 없음 (인메모리 모듈).
- **Config**: 환경 변수 신규 추가 없음 (Phase 2 의 `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` 그대로). main.py 데모 (Task 15) 가 GOOGLE_API_KEY 없으면 RuntimeError — 데모 호출 안 하면 영향 없음.
- **Worktree**: 코드 단계 진입 시 새 worktree (`.worktrees/phase-3-attachments-impl`) 생성 → 머지 후 cleanup. main 직접 작업 금지 (사용자 룰).

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-11 21:00] [구현계획서-수정]
- **id**: CH-20260511-001
- **이유**: 신규 구현 계획 (Phase 3 어태치먼트 시스템 — 16 task TDD, 12 신규 src + 4 변경 파일, 35~50 신규 테스트, 146~161 GREEN 목표)
- **무엇이**: phase-3-attachments-implementation-plan.md 전체 (§1 16 task + §2 8 위험 코드 지점 + §3 롤백 전략, commit_policy: per-task)
- **영향범위**: 없음 (최초 생성). PRD CH-20260508-001 + tech-design CH-20260510-001 의 FR-1..9 + NFR-1..4 + D1..D10 + R-1..R-8 + AC-1..12 모두 task 매핑 (verifying-spec PASS, code-pretty + docs-pretty 완료)
- **연관 항목**: CH-20260508-001 (PRD), CH-20260510-001 (tech-design)

### [2026-05-11 22:30] [코드-수정] (batch: Tasks 1..16, wave-parallel subagent-driven)
- **id**: CH-20260511-002
- **이유**: Phase 3 어태치먼트 시스템 16 task 구현 (5 dispatch wave + 메인 inline T16 검증). Subagent (haiku impl + sonnet spec reviewer) wave-parallel 실행.
- **무엇이**: 12 신규 src + 4 변경 파일 + 14 신규/확장 test 파일. **187 tests PASS, ruff clean**.
  - **신규 src**: messages.py, attachments/{__init__,protocol,registry,collect,counter,smoosh,gates,integrate}.py, attachments/builtins/{__init__,date_change,todo_reminder}.py
  - **변경 src**: prompts/render.py (RenderContext 슬롯 5개), main.py (call_with_attachments 데모)
  - **변경 test**: tests/conftest.py (restore_attachment_registry autouse), tests/test_no_domain_vocab.py (attachments/ + messages.py grep 확장)
  - **신규 test**: test_messages, test_attachments_{protocol,registry,collect,collect_timeout,counter,smoosh,gates,builtins_date,builtins_todo,helper_integration,full_flow,ctx_slots,init_purity,static_hash_invariant}
- **영향범위**: Phase 1 70 + Phase 2 41 = 111 회귀 0건 (R-6 backward compat 검증). Phase 3 +76 → 187 GREEN. Phase 2 LLMClient Protocol 시그니처 무변경 (D3 β 보존).
- **위험 카테고리**: side-effect 4 (R-3 wrap 책임 / R-4 BOUNDARY invariant / R-5 tool_call_id / R-8 thinking 식별 — 모두 design+test mitigation). race 2 (R-1 register 1회 / R-2 ctx frozen). breaking 1 (R-6 디폴트 값). perf 1 (R-7 1초 timeout 의도된 trade-off). RISK 코드 코멘트 추가 0건 (모두 design level mitigation).
- **세부 변경 (16 task)**:
  - Task 1 — Message + ContentBlock discriminated union (Pydantic frozen, Anthropic 거울)
  - Task 2 — Attachment Protocol + AttachmentGroup StrEnum (3 그룹)
  - Task 3 — AttachmentRegistry 싱글톤 + conftest snapshot fixture (Phase 1 거울)
  - Task 4 — RenderContext 슬롯 5개 (messages/todos/tool_pool/last_emit_date/is_subagent, R-6 backward compat)
  - Task 5 — collect_attachments 3그룹 병렬 + null + system-reminder wrap + 분기 (D9 spec deviation: wait_for(gather)→wait(ALL_COMPLETED), test_timeout_drops_slow_keeps_fast 가 fast 보존 요구)
  - Task 6 — count_turns_since (thinking 제외)
  - Task 7 — smoosh_into_last_tool_result (tool_call_id 보존)
  - Task 8 — register_tool_pool_gate + OR 평가 (gates.py 본 구현)
  - Task 9 — date_change builtin (자정 감지)
  - Task 10 — todo_reminder builtin (counter + gate 통합)
  - Task 11 — call_with_attachments helper β (Phase 2 LLMClient 시그니처 무변경)
  - Task 12 — NFR-1 grep 범위 attachments/ + messages.py 까지 확장
  - Task 13 — NFR-2 정적 캐시 안전 invariant 회귀 (R-4 mitigation)
  - Task 14 — NFR-4 init purity AST (D-13)
  - Task 15 — full flow 통합 + main.py call_with_attachments 데모
  - Task 16 — 메인 governance fix: registry test (builtin auto-register subset) + ruff clean
- **연관 항목**: CH-20260508-001 (PRD), CH-20260510-001 (tech-design), CH-20260511-001 (구현계획)
