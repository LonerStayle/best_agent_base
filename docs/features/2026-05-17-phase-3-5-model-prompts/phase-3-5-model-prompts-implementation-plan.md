---
commit_policy: per-task
---

# Phase 3.5 모델별 프롬프트 변형 슬롯 구현계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` (main-inline 사용자 명시) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RenderContext.model 슬롯 + @[MODEL:] 마커 런타임 필터 + 어댑터 자동 주입 — 모델별 프롬프트 변형 슬롯 (CC `getAntModelOverrideSection` 백엔드 포팅).

**Architecture:** 단일 helper (`filter_model_blocks`) + RenderContext.model 슬롯 + Phase 1 `_render_static`/`_render_dynamic` 통합 + Phase 2 어댑터 자동 model 주입. 정규식 단일 패턴 + fnmatch glob + non-greedy 매칭 + 중첩 거부.

**Tech Stack:** Python 3.12+, stdlib (`re`, `fnmatch`), Pydantic 2 frozen, pytest.

**Spec inputs:**
- phase-3-5-model-prompts-requirements.md (CH-20260517-001) — FR-1..6 + NFR-1..4 + AC-1..12
- phase-3-5-model-prompts-tech-design.md (CH-20260517-002) — D1..D7 결정 + R-1..R-5 리스크

---

## 1. 단계별 작업

### Task 1: filter_model_blocks 헬퍼

**Files:**
- Create: `best_agent_base/prompts/model_filter.py`
- Test: `tests/test_prompts_model_filter.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_prompts_model_filter.py
"""filter_model_blocks — @[MODEL: pattern] ... @[/MODEL] 마커 필터 (FR-2/3/6, D1/D2/D5/D6, R-1)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.model_filter import filter_model_blocks


def test_match_keeps_inner_content():
    out = filter_model_blocks("text @[MODEL: claude-*]ABC@[/MODEL] tail", "claude-sonnet-4-5-20250929")
    assert out == "text ABC tail"


def test_mismatch_strips_block():
    out = filter_model_blocks("text @[MODEL: claude-*]ABC@[/MODEL] tail", "gemini-2.5-flash")
    assert out == "text  tail"


def test_model_none_strips_all_blocks():
    out = filter_model_blocks("@[MODEL: *]X@[/MODEL]", None)
    assert out == ""


def test_no_markers_returns_unchanged():
    out = filter_model_blocks("plain text no markers", "claude-anything")
    assert out == "plain text no markers"


def test_two_consecutive_blocks_non_greedy():
    """R-1 — greedy 매칭이면 첫 @[/MODEL] 까지가 아니라 둘째 @[/MODEL] 까지 잘못 매칭됨."""
    text = "@[MODEL: claude-*]A@[/MODEL]@[MODEL: gemini-*]B@[/MODEL]"
    out_claude = filter_model_blocks(text, "claude-sonnet-4-5-20250929")
    assert out_claude == "A"  # claude block keep, gemini block strip
    out_gemini = filter_model_blocks(text, "gemini-2.5-flash")
    assert out_gemini == "B"


def test_glob_patterns_exact():
    text = "@[MODEL: claude-sonnet-4-*]X@[/MODEL]"
    assert filter_model_blocks(text, "claude-sonnet-4-5-20250929") == "X"
    assert filter_model_blocks(text, "claude-opus-4-7") == ""


def test_wildcard_matches_any():
    assert filter_model_blocks("@[MODEL: *]X@[/MODEL]", "claude-anything") == "X"
    assert filter_model_blocks("@[MODEL: *]X@[/MODEL]", "gemini-anything") == "X"


def test_nested_marker_raises():
    """FR-6 / D5 — 중첩 마커는 구조적 모호 → ValueError."""
    text = "@[MODEL: a]@[MODEL: b]X@[/MODEL]@[/MODEL]"
    with pytest.raises(ValueError, match="nested"):
        filter_model_blocks(text, "a")


def test_multiline_block_with_dotall():
    text = "@[MODEL: claude-*]\nline1\nline2\n@[/MODEL]"
    assert filter_model_blocks(text, "claude-anything") == "\nline1\nline2\n"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_prompts_model_filter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'best_agent_base.prompts.model_filter'`

- [ ] **Step 3: 최소 구현**

```python
# best_agent_base/prompts/model_filter.py
"""filter_model_blocks — @[MODEL: pattern] ... @[/MODEL] 마커 런타임 필터 (Phase 3.5 D1).

CC `getAntModelOverrideSection` 백엔드 포팅. 정규식 단일 패턴 (non-greedy + DOTALL) +
fnmatch glob 매칭. 단일 레벨 마커만 허용 (중첩 = ValueError, D5).
model=None 시 모든 마커 블록 strip (조용한 정규화, D2 — Phase 1~3 backward compat).
"""

from __future__ import annotations

import fnmatch
import re

# non-greedy `.*?` + re.DOTALL = 줄바꿈 포함 + R-1 greedy 함정 회피
_MARKER_RE = re.compile(r"@\[MODEL:\s*([^\]]+?)\s*\]\s*(.*?)\s*@\[/MODEL\]", re.DOTALL)
# 중첩 detect — 오프닝 두 번 연속 만나면 거부
_OPEN_RE = re.compile(r"@\[MODEL:\s*([^\]]+?)\s*\]")


def filter_model_blocks(text: str, model: str | None) -> str:
    """@[MODEL: pattern] ... @[/MODEL] 블록 fnmatch 매칭 시 inner content keep, 미매칭 시 전체 strip.

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
        # 다음 오프닝 위치 vs 다음 닫힘 위치 비교
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest tests/test_prompts_model_filter.py -v`
Expected: PASS — 9/9 tests

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/prompts/model_filter.py tests/test_prompts_model_filter.py
git commit -m "feat(prompts): filter_model_blocks helper — @[MODEL:] 마커 필터 (Task 1)"
```

---

### Task 2: RenderContext.model 슬롯 추가

**Files:**
- Modify: `best_agent_base/prompts/render.py:19-36`
- Test: 기존 `tests/test_attachments_ctx_slots.py` 확장 (한 줄 추가)

**Model**: haiku

- [ ] **Step 1: 회귀 + 신규 슬롯 테스트 추가**

`tests/test_attachments_ctx_slots.py` 끝에 추가:

```python
def test_model_slot_default_none():
    """Phase 3.5 — RenderContext.model 슬롯 디폴트 None."""
    ctx = RenderContext()
    assert ctx.model is None


def test_model_slot_accepts_string():
    ctx = RenderContext(model="claude-sonnet-4-5-20250929")
    assert ctx.model == "claude-sonnet-4-5-20250929"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_attachments_ctx_slots.py::test_model_slot_default_none tests/test_attachments_ctx_slots.py::test_model_slot_accepts_string -v`
Expected: FAIL — `AttributeError: 'RenderContext' object has no attribute 'model'`

- [ ] **Step 3: render.py 수정 — RenderContext 슬롯 추가**

**원본** (`best_agent_base/prompts/render.py:19-36`):

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

**수정 후**:

```python
class RenderContext(BaseModel):
    """베이스는 도메인/Phase 가 필드 추가하는 슬롯.

    Phase 3 어태치먼트 슬롯 5개 + Phase 3.5 model 슬롯 — 모두 디폴트 값 보유:
    - messages: 대화 기록 (어태치먼트가 카운터 / smoosh 시 읽음)
    - todos: TodoWrite 도구 (Phase 5+ OOS) 슬롯, todo_reminder 가 len() 만 봄 (D6)
    - tool_pool: 현재 등록된 도구 이름 집합 (도구 풀 게이트 평가용, FR-9)
    - last_emit_date: date_change 어태치먼트 자정 감지용
    - is_subagent: True 시 MAIN_THREAD 그룹 자동 제외 (원칙 #7)
    - model: 모델별 prompt 변형 (@[MODEL:] 마커 필터용, Phase 3.5 D1). 디폴트 None.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True, protected_namespaces=())

    messages: tuple = ()  # tuple[Message, ...] — Message import 시 순환 회피
    todos: tuple = ()  # tuple[Any, ...] — D6 (Phase 5+ 형식 미정 슬롯)
    tool_pool: frozenset[str] = frozenset()
    last_emit_date: date | None = None
    is_subagent: bool = False
    model: str | None = None  # Phase 3.5 — @[MODEL:] 마커 필터 / 어댑터 자동 주입 (D1, D3)
```

(`protected_namespaces=()` 추가 — Pydantic v2 가 `model_` 접두사 충돌 경고 회피)

- [ ] **Step 4: 테스트 통과 + Phase 1~3 회귀 확인**

Run: `uv run pytest tests/test_attachments_ctx_slots.py tests/test_prompts_render.py -v 2>&1 | tail -5`
Expected: PASS — 신규 2 + Phase 1/2/3 회귀 GREEN

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/prompts/render.py tests/test_attachments_ctx_slots.py
git commit -m "feat(prompts): RenderContext.model 슬롯 추가 (Task 2, R-3 backward compat)"
```

---

### Task 3: render(ctx) 통합 — filter_model_blocks 적용

**Files:**
- Modify: `best_agent_base/prompts/render.py:39-78` (_render_static / _render_dynamic)
- Test: `tests/test_prompts_model_aware_render.py`

**Model**: haiku

- [ ] **Step 1: 통합 테스트 작성**

```python
# tests/test_prompts_model_aware_render.py
"""render(ctx) 모델 통합 — filter_model_blocks 정적/동적 양쪽 적용 (FR-4, R-2, NFR-3)."""

from __future__ import annotations

import pytest

from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import RenderContext, _render_dynamic, _render_static, get_static_hash, render


class _ModelAwareSection:
    name = "Intro"  # override 베이스 Intro
    static = True

    def render(self, ctx):
        return "BASE @[MODEL: claude-*]CLAUDE@[/MODEL]@[MODEL: gemini-*]GEMINI@[/MODEL] TAIL"


def test_static_render_applies_filter_claude():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert "BASE CLAUDE TAIL" in out


def test_static_render_applies_filter_gemini():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext(model="gemini-2.5-flash"))
    assert "BASE GEMINI TAIL" in out


def test_static_render_model_none_strips_all():
    registry.register("Intro", _ModelAwareSection())
    out = _render_static(RenderContext())  # model=None
    assert "BASE  TAIL" in out  # 모든 마커 블록 strip
    assert "CLAUDE" not in out
    assert "GEMINI" not in out


def test_hash_differs_per_model_same_ctx_shape():
    """R-2 mitigation — 같은 모델 호출 시 동일 hash (캐시 적중), 다른 모델 다른 hash."""
    registry.register("Intro", _ModelAwareSection())
    h_claude = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    h_gemini = get_static_hash(RenderContext(model="gemini-2.5-flash"))
    h_none = get_static_hash(RenderContext())
    assert h_claude != h_gemini
    assert h_claude != h_none
    assert h_gemini != h_none


def test_hash_stable_same_model_repeated():
    registry.register("Intro", _ModelAwareSection())
    h1 = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    h2 = get_static_hash(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert h1 == h2


def test_dynamic_render_applies_filter():
    """동적 섹션도 filter 적용 — _render_dynamic 단독 호출 검증."""

    class _DynamicSection:
        name = "DynamicTest"
        static = False

        def render(self, ctx):
            return "@[MODEL: claude-*]CD@[/MODEL]@[MODEL: gemini-*]GD@[/MODEL]"

    registry.register("DynamicTest", _DynamicSection())
    out = _render_dynamic(RenderContext(model="claude-sonnet-4-5-20250929"))
    assert "CD" in out
    assert "GD" not in out
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_prompts_model_aware_render.py -v`
Expected: FAIL — filter 미적용으로 raw 텍스트에 `@[MODEL:` 마커 포함됨

- [ ] **Step 3: render.py 수정 — _render_static / _render_dynamic 에 filter 적용**

**원본** (`best_agent_base/prompts/render.py:39-78`):

```python
def _render_static(ctx: RenderContext) -> str:
    """정적 7섹션 (registry 기준) 을 순서대로 렌더링.

    도메인이 베이스 섹션을 `static=False` 로 override 하면 본 루프는 건너뛰고
    `_render_dynamic` 가 그 섹션을 잡아 BOUNDARY 뒤로 옮긴다 (정적→동적 강등).
    """
    parts: list[str] = []
    for base_section in BASE_SECTIONS:
        section = registry.get(base_section.name)
        if not section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(text)
    return "\n\n".join(parts)


def _render_dynamic(ctx: RenderContext) -> str:
    """동적 섹션을 합성. 베이스에는 없음 (Phase 1).

    도메인이 `static=False` section 을 register 한 경우 또는 베이스 섹션을
    `static=False` 로 override 한 경우 모두 본 루프가 잡는다. registry 의
    `all_sections()` 는 등록 순서로 반환 (Python 3.7+ dict insertion order).
    """
    parts: list[str] = []
    for section in registry.all_sections():
        if section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(text)
    return "\n\n".join(parts)
```

**수정 후**:

```python
def _render_static(ctx: RenderContext) -> str:
    """정적 7섹션 (registry 기준) 을 순서대로 렌더링.

    도메인이 베이스 섹션을 `static=False` 로 override 하면 본 루프는 건너뛰고
    `_render_dynamic` 가 그 섹션을 잡아 BOUNDARY 뒤로 옮긴다 (정적→동적 강등).
    Phase 3.5: 각 섹션 결과에 filter_model_blocks(text, ctx.model) 적용 (D1, D4 hash 시점).
    """
    parts: list[str] = []
    for base_section in BASE_SECTIONS:
        section = registry.get(base_section.name)
        if not section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(filter_model_blocks(text, ctx.model))
    return "\n\n".join(parts)


def _render_dynamic(ctx: RenderContext) -> str:
    """동적 섹션을 합성. 베이스에는 없음 (Phase 1).

    도메인이 `static=False` section 을 register 한 경우 또는 베이스 섹션을
    `static=False` 로 override 한 경우 모두 본 루프가 잡는다. registry 의
    `all_sections()` 는 등록 순서로 반환 (Python 3.7+ dict insertion order).
    Phase 3.5: 각 섹션 결과에 filter_model_blocks(text, ctx.model) 적용.
    """
    parts: list[str] = []
    for section in registry.all_sections():
        if section.static:
            continue
        text = section.render(ctx)
        if SYSTEM_PROMPT_DYNAMIC_BOUNDARY in text:
            raise ValueError(
                f"section {section.name!r} render output contains the boundary marker "
                f"({SYSTEM_PROMPT_DYNAMIC_BOUNDARY!r}); domain content must not include it."
            )
        parts.append(filter_model_blocks(text, ctx.model))
    return "\n\n".join(parts)
```

추가 import (파일 상단, `from best_agent_base.prompts.registry import registry` 아래):

```python
from best_agent_base.prompts.model_filter import filter_model_blocks
```

- [ ] **Step 4: 테스트 통과 + 회귀**

Run: `uv run pytest tests/test_prompts_model_aware_render.py tests/test_prompts_render.py tests/test_prompts_static_stability.py tests/test_cache_key_stability.py -v 2>&1 | tail -5`
Expected: PASS — 신규 6 + Phase 1/2/3 회귀 GREEN (Phase 1 default sections 에 마커 없음 → filter 통과 시 그대로)

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/prompts/render.py tests/test_prompts_model_aware_render.py
git commit -m "feat(prompts): render(ctx) 모델 필터 통합 (Task 3, R-2 hash 격리)"
```

---

### Task 4: GeminiClient 자동 model 주입

**Files:**
- Modify: `best_agent_base/llm/gemini.py:83-90` (generate 함수 시작)
- Test: `tests/test_llm_adapter_model_injection.py`

**Model**: haiku

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_llm_adapter_model_injection.py
"""LLMClient 어댑터 자동 model 주입 — Gemini / Anthropic (FR-5, D3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from best_agent_base.llm.client import LLMResponse, TokenUsage
from best_agent_base.prompts.render import RenderContext


@pytest.mark.asyncio
async def test_gemini_auto_injects_model_when_none(monkeypatch):
    """GeminiClient.generate(ctx with model=None) → 어댑터가 self._profile.model.value 자동 주입."""
    from best_agent_base.llm import gemini as gemini_mod

    fake_sdk = MagicMock()
    fake_result = MagicMock()
    fake_result.text = "ok"
    fake_result.usage_metadata = MagicMock(
        prompt_token_count=1, candidates_token_count=1, cached_content_token_count=0
    )
    fake_sdk.aio.models.generate_content = AsyncMock(return_value=fake_result)
    fake_sdk.aio.caches.create = AsyncMock(side_effect=Exception("no cache for this test"))

    monkeypatch.setattr(gemini_mod, "_build_genai_client", lambda: fake_sdk)

    client = gemini_mod.GeminiClient()
    expected_model = client._profile.model.value

    captured_ctx: list[RenderContext] = []
    orig_split = gemini_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(gemini_mod, "split_at_boundary", spy_split)

    await client.generate(RenderContext())  # ctx.model=None

    assert captured_ctx[0].model == expected_model


@pytest.mark.asyncio
async def test_gemini_respects_explicit_model(monkeypatch):
    """ctx.model 명시 시 어댑터 자동 주입 우회 (도메인 우선, D3)."""
    from best_agent_base.llm import gemini as gemini_mod

    fake_sdk = MagicMock()
    fake_result = MagicMock()
    fake_result.text = "ok"
    fake_result.usage_metadata = MagicMock(
        prompt_token_count=1, candidates_token_count=1, cached_content_token_count=0
    )
    fake_sdk.aio.models.generate_content = AsyncMock(return_value=fake_result)
    fake_sdk.aio.caches.create = AsyncMock(side_effect=Exception("no cache"))

    monkeypatch.setattr(gemini_mod, "_build_genai_client", lambda: fake_sdk)
    client = gemini_mod.GeminiClient()

    captured_ctx: list[RenderContext] = []
    orig_split = gemini_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(gemini_mod, "split_at_boundary", spy_split)

    await client.generate(RenderContext(model="my-custom-model"))

    assert captured_ctx[0].model == "my-custom-model"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_llm_adapter_model_injection.py::test_gemini_auto_injects_model_when_none tests/test_llm_adapter_model_injection.py::test_gemini_respects_explicit_model -v`
Expected: FAIL — `assert None == 'gemini-...'` (ctx.model 그대로 None 전달됨)

- [ ] **Step 3: gemini.py 수정 — generate 시작에 자동 주입**

**원본** (`best_agent_base/llm/gemini.py:83-90`):

```python
    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
```

**수정 후**:

```python
    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        # Phase 3.5 — ctx.model 없으면 자기 model 자동 주입 (D3, FR-5)
        if ctx.model is None:
            ctx = ctx.model_copy(update={"model": self._profile.model.value})
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
```

- [ ] **Step 4: 테스트 통과 + Phase 2 회귀**

Run: `uv run pytest tests/test_llm_adapter_model_injection.py tests/test_gemini_adapter.py -v 2>&1 | tail -5`
Expected: PASS — Gemini 신규 2 + Phase 2 Gemini 회귀 GREEN

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/llm/gemini.py tests/test_llm_adapter_model_injection.py
git commit -m "feat(llm): GeminiClient 자동 model 주입 (Task 4, FR-5/D3)"
```

---

### Task 5: AnthropicClient 자동 model 주입

**Files:**
- Modify: `best_agent_base/llm/anthropic.py:50-62` (generate 함수 시작)
- Test: `tests/test_llm_adapter_model_injection.py` (확장)

**Model**: haiku

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_llm_adapter_model_injection.py` 끝에 추가:

```python
@pytest.mark.asyncio
async def test_anthropic_auto_injects_model_when_none(monkeypatch):
    """AnthropicClient.generate(ctx with model=None) → 어댑터가 self._model 자동 주입."""
    from best_agent_base.llm import anthropic as anth_mod

    fake_sdk = MagicMock()
    fake_block = MagicMock()
    fake_block.text = "ok"
    fake_result = MagicMock()
    fake_result.content = [fake_block]
    fake_result.usage = MagicMock(
        input_tokens=1, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )
    fake_sdk.messages.create = AsyncMock(return_value=fake_result)

    monkeypatch.setattr(anth_mod, "_build_anthropic_client", lambda: fake_sdk)
    client = anth_mod.AnthropicClient()
    expected_model = client._model

    captured_ctx: list[RenderContext] = []
    orig_split = anth_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(anth_mod, "split_at_boundary", spy_split)

    await client.generate(RenderContext())  # ctx.model=None

    assert captured_ctx[0].model == expected_model


@pytest.mark.asyncio
async def test_anthropic_respects_explicit_model(monkeypatch):
    """ctx.model 명시 시 어댑터 자동 주입 우회."""
    from best_agent_base.llm import anthropic as anth_mod

    fake_sdk = MagicMock()
    fake_block = MagicMock()
    fake_block.text = "ok"
    fake_result = MagicMock()
    fake_result.content = [fake_block]
    fake_result.usage = MagicMock(
        input_tokens=1, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0
    )
    fake_sdk.messages.create = AsyncMock(return_value=fake_result)

    monkeypatch.setattr(anth_mod, "_build_anthropic_client", lambda: fake_sdk)
    client = anth_mod.AnthropicClient()

    captured_ctx: list[RenderContext] = []
    orig_split = anth_mod.split_at_boundary

    def spy_split(ctx):
        captured_ctx.append(ctx)
        return orig_split(ctx)

    monkeypatch.setattr(anth_mod, "split_at_boundary", spy_split)

    await client.generate(RenderContext(model="my-custom-model"))

    assert captured_ctx[0].model == "my-custom-model"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest tests/test_llm_adapter_model_injection.py::test_anthropic_auto_injects_model_when_none tests/test_llm_adapter_model_injection.py::test_anthropic_respects_explicit_model -v`
Expected: FAIL

- [ ] **Step 3: anthropic.py 수정**

**원본** (`best_agent_base/llm/anthropic.py:50-62`):

```python
    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        """Phase 1 render(ctx) 출력을 Anthropic Messages API 로 호출, 캐싱 정책 반영.

        Raises: anthropic SDK 예외 (BadRequestError / RateLimitError / etc.) 그대로 전파 (D6).
        에러 envelope 변환은 도구 베이스 Phase 의 본질이라 본 어댑터에서 흡수하지 않음.
        """
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
        key = get_static_hash(ctx)
```

**수정 후**:

```python
    async def generate(
        self,
        ctx: RenderContext,
        *,
        cache_policy: CachePolicy | None = None,
    ) -> LLMResponse:
        """Phase 1 render(ctx) 출력을 Anthropic Messages API 로 호출, 캐싱 정책 반영.

        Raises: anthropic SDK 예외 (BadRequestError / RateLimitError / etc.) 그대로 전파 (D6).
        에러 envelope 변환은 도구 베이스 Phase 의 본질이라 본 어댑터에서 흡수하지 않음.
        Phase 3.5: ctx.model 없으면 self._model 자동 주입 (D3, FR-5).
        """
        # Phase 3.5 — ctx.model 없으면 자기 model 자동 주입
        if ctx.model is None:
            ctx = ctx.model_copy(update={"model": self._model})
        policy = cache_policy if cache_policy is not None else CachePolicy()
        static_text, dynamic_text = split_at_boundary(ctx)
        key = get_static_hash(ctx)
```

- [ ] **Step 4: 테스트 통과 + Phase 2 회귀**

Run: `uv run pytest tests/test_llm_adapter_model_injection.py tests/test_anthropic_adapter.py -v 2>&1 | tail -5`
Expected: PASS — Anthropic 신규 2 (Gemini 2 + Anthropic 2 = 4 총) + Phase 2 Anthropic 회귀 GREEN

- [ ] **Step 5: 커밋**

```bash
git add best_agent_base/llm/anthropic.py tests/test_llm_adapter_model_injection.py
git commit -m "feat(llm): AnthropicClient 자동 model 주입 (Task 5, FR-5/D3)"
```

---

### Task 6: NFR-1 grep 범위 확장 + 최종 GREEN

**Files:**
- Modify: `tests/test_no_domain_vocab.py` (grep 범위 + MODEL_FILTER_FILE 추가)

**Model**: haiku

- [ ] **Step 1: 신규 파일 grep 검증 추가**

`tests/test_no_domain_vocab.py` 끝에 추가:

```python
MODEL_FILTER_FILE = PROJECT_ROOT / "best_agent_base" / "prompts" / "model_filter.py"


@pytest.mark.parametrize("term", FORBIDDEN_TERMS)
def test_model_filter_file_free_of_domain_vocab(term):
    """Phase 3.5 — model_filter.py 도 도메인 중립성 (NFR-1)."""
    assert not _scan_file(term, MODEL_FILTER_FILE), (
        f"forbidden domain term {term!r} found in model_filter.py"
    )


def test_model_filter_file_exists():
    assert MODEL_FILTER_FILE.is_file()
```

(추가 grep — `prompts/` 디렉토리 전체에 `claude-*`, `gemini-*` 같은 도메인 모델 이름 박혀 있는지 검사):

```python
DOMAIN_MODEL_PATTERNS = (
    "claude-",
    "gemini-",
)


@pytest.mark.parametrize("pattern", DOMAIN_MODEL_PATTERNS)
def test_prompts_dir_free_of_domain_model_names(pattern):
    """NFR-1 — 베이스 prompts/ 안에 도메인 모델 이름 박지 않음.

    어댑터 (llm/) 는 자기 model 이름 박혀있어도 OK — 예외 처리.
    """
    import re as _re

    pat = _re.compile(_re.escape(pattern), _re.IGNORECASE)
    hits: list[Path] = []
    for py in PROMPTS_DIR.rglob("*.py"):
        if pat.search(py.read_text(encoding="utf-8")):
            hits.append(py)
    assert not hits, (
        f"domain model pattern {pattern!r} found in base prompts dir: "
        f"{[str(h.relative_to(PROJECT_ROOT)) for h in hits]}"
    )
```

- [ ] **Step 2: 테스트 실행**

Run: `uv run pytest tests/test_no_domain_vocab.py -v 2>&1 | tail -5`
Expected: PASS — 신규 11 (FORBIDDEN_TERMS 9 + existence 1 + DOMAIN_MODEL 2) 모두 GREEN

- [ ] **Step 3: 전체 GREEN + ruff clean 검증**

Run:
```bash
uv run pytest 2>&1 | tail -3
uv run ruff check best_agent_base/ tests/ main.py 2>&1 | tail -3
```
Expected: 모든 테스트 PASS (예상 211 +/- 5), ruff clean

- [ ] **Step 4: Phase 1~3 회귀 None 확인**

Run: `uv run pytest tests/test_prompts_render.py tests/test_prompts_static_stability.py tests/test_cache_key_stability.py tests/test_gemini_adapter.py tests/test_anthropic_adapter.py tests/test_attachments_static_hash_invariant.py -v 2>&1 | tail -5`
Expected: Phase 1/2/3 모든 회귀 GREEN

- [ ] **Step 5: 커밋**

```bash
git add tests/test_no_domain_vocab.py
git commit -m "test(no-domain-vocab): model_filter.py + prompts/ 모델 이름 grep 확장 (Task 6, NFR-1)"
```

---

## 2. 위험 코드 지점

tech-design §6 R-1..R-5 → file:line + mitigation 매핑.

- `best_agent_base/prompts/model_filter.py:_MARKER_RE` — **side-effect**: 정규식 greedy 매칭으로 2 연속 블록 잘못 합침. Mitigation: `(.*?)` non-greedy + `re.DOTALL` 사용, 단위 테스트 `test_two_consecutive_blocks_non_greedy`.
- `best_agent_base/prompts/render.py:_render_static` / `_render_dynamic` — **side-effect**: filter_model_blocks 결과를 hash 입력으로 사용 → 같은 ctx 반복 호출 시 동일 hash 보장 필요. Mitigation: 회귀 테스트 `test_hash_stable_same_model_repeated` + 어댑터 자동 주입으로 None fallback 케이스 최소화.
- `best_agent_base/prompts/render.py:RenderContext` — **breaking**: 슬롯 추가가 Phase 1~3 (`RenderContext()` 호출 11+ 사이트) 깨뜨림? Mitigation: 디폴트 None + 회귀 187 GREEN 검증 (`test_attachments_ctx_slots` 확장).
- `best_agent_base/prompts/model_filter.py` — **perf**: 매 render 마다 정규식 매칭 — 텍스트 짧음 (< 수 KB) + compiled pattern 캐싱. NFR 명시 없음 (의도된 trade-off).
- `best_agent_base/llm/{gemini,anthropic}.py:generate` — **side-effect**: 자동 주입이 도메인 의도 가림 — ctx.model=None 의도라도 어댑터가 자기 model 로 채움. Mitigation: 도메인이 sentinel 박는 패턴은 OOS-8 명시, 인터페이스 가이드에 자동 주입 동작 명시.

## 3. 롤백 전략

- **Code**: per-task atomic commit — 문제 task 만 `git revert <SHA>`. Phase 1~3 회귀 깨지면 Task 2 (RenderContext 슬롯) 우선 revert.
- **DB**: 변경 없음 (인메모리).
- **Config**: 환경 변수 추가 X.
- **Worktree**: 작은 mini-phase + main-inline → worktree 미사용 (코드 단계 main 직접 — 사용자 명시).

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-17 13:00] [구현계획서-수정]
- **id**: CH-20260517-003
- **이유**: Phase 3.5 mini-phase 구현 계획 (6 task TDD, 1 신규 src + 3 변경 src + 4 신규/확장 test, ~211 GREEN 목표)
- **무엇이**: phase-3-5-model-prompts-implementation-plan.md 전체 (§1 6 task + §2 5 위험 코드 지점 + §3 롤백, commit_policy: per-task)
- **영향범위**: 없음 (최초 생성). PRD CH-20260517-001 + tech-design CH-20260517-002 의 FR-1..6 + NFR-1..4 + D1..D7 + R-1..R-5 + AC-1..12 모두 task 매핑 (verify PASS, 메인 직접). 사용자 자동 진행 모드 — main-inline 실행 (작은 mini-phase, worktree 미사용).
- **연관 항목**: CH-20260517-001 (PRD), CH-20260517-002 (tech-design)

### [2026-05-17 13:30] [코드-수정] (batch: Tasks 1..6, main-inline)
- **id**: CH-20260517-004
- **이유**: Phase 3.5 mini-phase 6 task 구현 (main-inline, 사용자 자동 진행). 모든 task TDD RED → GREEN → commit.
- **무엇이**: 1 신규 src + 3 변경 src + 4 신규/확장 test. **220 tests PASS, ruff clean**.
  - 신규 src: `best_agent_base/prompts/model_filter.py`
  - 변경 src: `best_agent_base/prompts/render.py` (RenderContext.model 슬롯 + _render_static/_dynamic filter 적용), `best_agent_base/llm/gemini.py` (자동 주입), `best_agent_base/llm/anthropic.py` (자동 주입)
  - 신규 test: `test_prompts_model_filter.py` (9), `test_prompts_model_aware_render.py` (6), `test_llm_adapter_model_injection.py` (4)
  - 확장 test: `test_attachments_ctx_slots.py` (+2), `test_no_domain_vocab.py` (+12 — model_filter grep 9 + existence 1 + DOMAIN_MODEL 2)
- **영향범위**: Phase 1 70 + Phase 2 41 + Phase 3 76 = 187 회귀 0건 (R-3 backward compat 검증). Phase 3.5 +33 → 220 GREEN. Phase 2 LLMClient Protocol 시그니처 무변경 (D3 model_copy 보존).
- **위험 카테고리**: side-effect 3 (R-1 정규식 non-greedy / R-2 hash 격리 / R-5 자동 주입 의도 가림). breaking 1 (R-3 슬롯 추가 — 디폴트 None). perf 1 (R-4 정규식 매번 — 의도된 trade-off). RISK 코드 코멘트 추가 0건 (모두 design level + 테스트 mitigation).
- **세부 변경 (6 task)**:
  - Task 1 — filter_model_blocks 헬퍼 (정규식 non-greedy + DOTALL + fnmatch + 중첩 거부)
  - Task 2 — RenderContext.model 슬롯 (`str | None = None` + protected_namespaces=())
  - Task 3 — render() 통합 (_render_static / _render_dynamic 양쪽 filter)
  - Task 4 — GeminiClient 자동 주입 (model_copy frozen ctx)
  - Task 5 — AnthropicClient 자동 주입 (model_copy frozen ctx)
  - Task 6 — NFR-1 grep 확장 + ruff cleanup
- **연관 항목**: CH-20260517-001 (PRD), CH-20260517-002 (tech-design), CH-20260517-003 (구현계획)
