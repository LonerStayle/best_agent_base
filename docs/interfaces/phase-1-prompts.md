# `best_agent_base.prompts` — 인터페이스 가이드

> **공식 인터페이스 개발문서**. 도메인 프로젝트가 `best_agent_base.prompts` 를 import 해서 자기 에이전트의 시스템 프롬프트를 구성할 때 참조한다.

---

## 1. 모듈 책임

7섹션 시스템 프롬프트의 **도메인-중립 골격 + 정적/동적 분리 + 캐시 측정 슬롯** 을 제공한다. 콘텐츠는 도메인이 `register`/`override` 로 주입.

---

## 2. 사용 예시

### 2.1 가장 단순한 사용 — 베이스 그대로

```python
from best_agent_base.prompts.render import RenderContext, render

prompt = render(RenderContext())
# → 7섹션 + BOUNDARY + 빈 동적부 (도메인-중립 콘텐츠)
llm.chat(system=prompt, user_messages=[...])
```

### 2.2 도메인 콘텐츠 주입 (가장 흔한 패턴)

```python
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render   import RenderContext, render

class CodingDoingTasks:
    name = "DoingTasks"
    static = True
    def render(self, ctx):
        return (
            "# Doing tasks\n"
            "- Use type hints; prefer composition over inheritance.\n"
            "- Write tests first (RED → GREEN → commit)."
        )

class CodingIntro:
    name = "Intro"
    static = True
    def render(self, ctx):
        return "You are a senior Python coding assistant. ..."

# 앱 부트스트랩 시 1회 등록 (싱글톤이라 register-once-then-read-many)
registry.register("Intro", CodingIntro())
registry.register("DoingTasks", CodingDoingTasks())

# 이후 매 요청마다
prompt = render(RenderContext())
```

### 2.3 동적 섹션 (정적 hash 안전)

```python
import time

class DynamicTimestamp:
    name = "DynamicTimestamp"
    static = False                                  # ← 동적부로 분류
    def render(self, ctx):
        return f"[runtime] now = {time.time():.0f}"

registry.register("DynamicTimestamp", DynamicTimestamp())

prompt = render(RenderContext())
# → BOUNDARY 뒤에 timestamp 줄 추가됨. 정적 hash 는 그대로 유지 (캐시 안전)
```

### 2.4 캐시 측정 (캐시 메트릭 모듈과 결합 예고)

```python
from best_agent_base.prompts.render import RenderContext, get_static_hash, render

ctx = RenderContext()
cache_key = get_static_hash(ctx)        # "fdb02d2a4245727e"
prompt    = render(ctx)

# 캐시 메트릭 모듈 (예정): cache_key 로 KV 캐시 hit/miss 추적
metrics.record_request(cache_key=cache_key)
```

---

## 3. 핵심 개념

### 3.1 정적/동적 분리 (D-1)

```
┌──────────────── render(ctx) 결과 ────────────────┐
│                                                  │
│  <정적 7섹션>                ← 매 turn 동일       │
│   §1 Intro                     KV 캐시 적중       │
│   §2 System                    get_static_hash() │
│   §3 DoingTasks                의 입력 → 캐시 키  │
│   §4 ExecutingActions                            │
│   §5 UsingTools                                  │
│   §6 ToneStyle                                   │
│   §7 OutputEfficiency                            │
│                                                  │
│  __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__              │
│                                                  │
│  <동적부>                    ← 매 turn 변경 가능 │
│   (현재 베이스에는 비어있음)                       │
│   (도메인이 static=False 로 register 한 섹션 등) │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 3.2 register/override (D-8)

```
                         ┌────── 베이스 ──────┐
                         │ BASE_SECTIONS      │
                         │   = (Intro,System, │
                         │      DoingTasks,…) │
                         └─────────┬──────────┘
                                   │ 모듈 로딩 시 자동 register
                                   ▼
                         ┌─────────────────────┐
                         │ SectionRegistry     │
                         │   _sections: dict   │
                         │   "Intro" → 베이스   │
                         │   "DoingTasks" → 베  │ ◀────┐
                         │   ...               │      │ register(name, custom)
                         └─────────────────────┘      │
                                   ▲                  │
                                   │ get(name)        │
                                   │                  │
                         ┌─────────┴──────────┐  ┌────┴───────────────┐
                         │ render(ctx)        │  │ Domain Project     │
                         │  ↓ _render_static  │  │  CodingDoingTasks  │
                         │  ↓ _render_dynamic │  │  MedicalIntro      │
                         │  → str             │  │  ...               │
                         └────────────────────┘  └────────────────────┘
```

### 3.3 dangerous_uncached escape hatch (R-4)

```
   원칙: 정적 영역 = 모든 turn 동일 → KV 캐시 hit
   
   예외: "정적 영역" 정책상 거기 있어야 하는데 매 turn 변하는 데이터
         (예: session ID, 인증 토큰 hash)
   
       ┌─ 잘못된 방법 ─────────────────┐
       │ class DynamicIntro:           │  ← 정적 자리에 임의 동적 데이터
       │     name = "Intro"            │     → 매 turn hash 변함
       │     static = True             │     → 캐시 평생 miss (R-3)
       │     def render(self, ctx):    │
       │         return f"now {now()}" │
       └───────────────────────────────┘
       
       ┌─ 올바른 방법 ──────────────────────────────────────────────┐
       │ section = dangerous_uncached(                              │
       │     name="session",                                        │
       │     content=f"session_id: {session_id}",                   │
       │     reason="static 영역에 세션ID 박는 보안 정책             │
       │             (hooks 시스템에서 모니터링)",                   │
       │     # ← reason 빈 문자 거부 (R-4)                           │
       │ )                                                          │
       │ registry.register("session", section)                      │
       │   → 의도가 명시되고 reason 이 추적 가능                       │
       └────────────────────────────────────────────────────────────┘
```

---

## 4. 확장 포인트

| 무엇 | 어떻게 |
|---|---|
| 베이스 7섹션 중 1개 콘텐츠 갈아끼우기 | `class X: name="<one of 7>"; static=True; def render(...)` 후 `registry.register("<name>", X())` |
| 새 동적 섹션 추가 | 위와 동일하되 `static = False` |
| RenderContext 필드 추가 | `class MyCtx(RenderContext): tools: list[ToolSpec]` 후 `MyCtx(tools=[...])` 로 호출 |
| 정적 영역에 cache-break 필요 | `dangerous_uncached(name=..., content=..., reason=...)` 후 register |
| 도메인 ctx 의 필드를 섹션이 사용 | `def render(self, ctx): return f"tools: {ctx.tools}"` |

**금지**:
- ❌ 베이스 `__init__.py` 에 import/re-export 추가 (D-13)
- ❌ `_BaseSection` 같은 베이스 내부 클래스 상속 (Protocol 만 만족하면 됨)
- ❌ `registry._sections` 직접 mutate (production 코드에서. 테스트 isolation 시는 OK)
- ❌ `reason=""` 으로 `dangerous_uncached` 우회 (Pydantic validation 으로 차단)

---

## 5. 위험·주의사항

| ID | 카테고리 | 도메인 사용자 체크포인트 |
|----|---------|-----------------------|
| **R-1** | race | 현재 `registry` 는 **register-once-then-read-many** 가정 (앱 부트스트랩 시 1회 등록). 멀티-요청 서버 환경에서 매 요청마다 register 호출하지 말 것. API 노출 모듈 합류 시점에 ContextVar 기반 per-request 격리로 전환 예정. |
| **R-3** | perf | 정적 섹션 (`static=True`) 의 `render()` 안에서 **동적 데이터** (현재시각/랜덤 ID/카운터) 사용 금지. 사용해야 하면 `dangerous_uncached` 로 명시 또는 `static=False` 로 분류. |
| **R-4** | side-effect | `dangerous_uncached(reason="")` 거부됨. reason 은 인스펙션·로깅 대상 — 의미있게 작성. |
| **R-5** | side-effect | 도메인 섹션의 `render()` 출력에 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 문자열 우연 포함 시 `render()` 가 ValueError. 에러 메시지에 어느 섹션인지 표시됨. |
| **R-7** | side-effect | `ExecutingActions` 섹션 override 시 베이스 default 의 안전 가드 ("irreversible 작업은 confirm" 등) 보다 약해지지 않도록 주의. 베이스 텍스트 안에 WARNING 문구 박혀있음. |

---

## 6. 다른 모듈과의 연계

| 연계 모듈 | 연계 지점 |
|---|---|
| **캐시 메트릭 (KV 캐시 측정)** | `get_static_hash(ctx)` 를 cache key 로 → KV 캐시 hit/miss 측정. `RenderContext` 에 `cache_request_id` 같은 필드 추가 가능 (forward-compatible). |
| **도구 시스템** | `RenderContext.tools: list[ToolSpec]` 추가 → `UsingTools` 섹션이 동적 도구 카탈로그 렌더 (`static=False` 로 override). |
| **컨텍스트 관리 (어태치먼트·압축)** | `RenderContext.attachments: list[Attachment]` 추가 → 동적 섹션이 첨부 메타 주입. |
| **Hooks 시스템** | `dangerous_uncached.reason` 들을 모아 모니터링 — 캐시 부채 가시화. |
| **API 노출 (FastAPI)** | `SectionRegistry` 를 ContextVar 기반 per-request 격리로 전환 (R-1 mitigation). 현재 API 시그니처는 유지될 가능성 높음 (forward-compatible). |

---

## 7. 데모 노트북 / 참조 코드

- **데모 노트북**: [`notebooks/phase-1-prompts-demo.ipynb`](../../notebooks/phase-1-prompts-demo.ipynb) — 1부(베이스) → 2부(도메인 override) → 3부(dangerous_uncached + 동적) → 4부(R-5 가드) → cleanup → 다른 모듈 연계 + 실습 4개
- **참조 테스트** (사용 패턴 학습용):
  - `tests/test_prompts_sections.py` — Protocol 만족 검증
  - `tests/test_prompts_registry.py` — register/override 패턴
  - `tests/test_prompts_render.py` — render 조립 + R-5 가드
  - `tests/test_prompts_static_stability.py` — 정적 안정성
  - `tests/test_prompts_dangerous_uncached.py` — escape hatch + reason 검증

---

## 8. Public API (Reference)

> 전체 import 가능 심볼. 위 §2 사용 예시로 감 잡은 후 reference 로 참고.

### 8.1 `best_agent_base.prompts.sections`

```python
from typing import Protocol, runtime_checkable
from best_agent_base.prompts.render import RenderContext

@runtime_checkable
class PromptSection(Protocol):
    """시스템 프롬프트의 한 섹션. 베이스/도메인 모두 이 형태를 만족해야 한다."""
    name: str                                       # registry 키
    static: bool                                    # True → 캐시 영역, False → 동적부
    def render(self, ctx: RenderContext) -> str: ...

# 7 베이스 섹션 인스턴스 (모두 static=True)
Intro             : PromptSection
System            : PromptSection
DoingTasks        : PromptSection
ExecutingActions  : PromptSection                   # WARNING: override 시 안전 가드 약화 금지
UsingTools        : PromptSection
ToneStyle         : PromptSection
OutputEfficiency  : PromptSection

BASE_SECTIONS: tuple[PromptSection, ...]            # 위 7개 (정적부 렌더링 순서)
```

### 8.2 `best_agent_base.prompts.registry`

```python
class SectionRegistry:
    def register(self, name: str, section: PromptSection) -> None
    def get(self, name: str) -> PromptSection                      # 미등록 → KeyError
    def all_sections(self) -> Iterable[PromptSection]              # 등록 순서

registry: SectionRegistry                            # 모듈-레벨 싱글톤
                                                     # 모듈 로딩 시 BASE_SECTIONS 7개 자동 등록
```

### 8.3 `best_agent_base.prompts.render`

```python
from pydantic import BaseModel, ConfigDict

class RenderContext(BaseModel):
    """베이스는 빈 frozen 모델. 도메인이 필드 추가."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

def render(ctx: RenderContext) -> str
    """
    조립: <정적 7섹션> \\n\\n __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ \\n\\n <동적부>
    sync 영구 (D1-7=δ). 도메인 비동기 fetch 는 호출자 책임.
    raises ValueError: 섹션 콘텐츠에 BOUNDARY 마커 우연 포함 시 (R-5)
    """

def get_static_hash(ctx: RenderContext) -> str
    """정적 섹션 묶음의 sha256 hex digest 첫 16자.
    KV 캐시 적중률 측정 모듈 (`best_agent_base.cache`) 의 cache key 후보."""
```

### 8.4 `best_agent_base.prompts.boundary`

```python
SYSTEM_PROMPT_DYNAMIC_BOUNDARY: str = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"
# CC 와 정확히 동일 문자열 (D1-6). split 마커 용도.

class DangerousUncached(BaseModel):
    """정적 영역에 들어가지만 의도적으로 캐시 깨는 섹션. PromptSection 만족."""
    model_config = ConfigDict(frozen=True)
    name: str        # min_length=1
    content: str
    reason: str      # min_length=1 ← R-4 — 빈 문자열 거부
    static: bool = True
    def render(self, ctx) -> str  # returns self.content

def dangerous_uncached(*, name: str, content: str, reason: str) -> DangerousUncached
    """정적 영역에 캐시 비친화 콘텐츠를 의도적으로 넣을 때만 사용 (키워드-only)."""
```

### 8.5 import 룰

베이스 `__init__.py` 들은 **docstring-only** (D-13). re-export 없음. 풀 경로 import 필수:

```python
from best_agent_base.prompts.sections   import PromptSection, BASE_SECTIONS
from best_agent_base.prompts.registry   import registry
from best_agent_base.prompts.render     import render, get_static_hash, RenderContext
from best_agent_base.prompts.boundary   import (
    SYSTEM_PROMPT_DYNAMIC_BOUNDARY,
    dangerous_uncached,
    DangerousUncached,
)
```
