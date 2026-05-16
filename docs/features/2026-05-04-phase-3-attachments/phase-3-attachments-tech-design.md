# 개발방향: Phase 3 — 어태치먼트 시스템 (사용자 입력 + ReAct 라운드 양 지점)

> **For agentic workers:** This document is the technical spec (architecture, components, data, interfaces, decisions, risks, test strategy). It is anchored to `phase-3-attachments-requirements.md` (the PRD, CH-20260508-001) and consumed by `phase-3-attachments-implementation-plan.md` (step-by-step plan). NEXT STEP: invoke `writing-plans` skill (or run `/write-plan`) to produce `phase-3-attachments-implementation-plan.md` from this design. Do NOT include step-by-step implementation tasks here — those belong in the plan.

## 1. 아키텍처 개요

### 다이어그램

```
                ┌────────────────────────────────────────┐
                │   도메인 코드 (의료/금융/코딩 etc.)    │
                └────────────────┬───────────────────────┘
                                 │
                                 ▼
              call_with_attachments(client, ctx, user_input)
                                 │
            ┌────────────────────┼─────────────────────┐
            ▼                                          ▼
  collect_attachments(ctx, user_input=...)   client.generate(new_ctx)
            │                                          │
            │                                          ▼
            │                          Phase 2: GeminiClient/AnthropicClient
            │                                          │
            ▼                                          ▼
   asyncio.wait_for(gather, 1.0s)         split_at_boundary(ctx)
            │                                          │
   ┌────────┼────────┬──────────┐                      ▼
   ▼        ▼        ▼          ▼            ┌──────────────────┐
USER_INPUT ALL_THREAD MAIN_THREAD            │  static = 정적7  │
   │        │        │                       │  ─ BOUNDARY ─    │
   ▼        ▼        ▼                       │  dynamic = ctx   │
 build()  build()  build()                   │  .messages 등    │
   │        │        │                       └──────────────────┘
   │ (None 자동 제외 / SystemReminder wrap)
   ▼
list[Message] (role="user", <system-reminder>)
            │
            ▼
   ctx.messages 에 합쳐 new_ctx 생성
```

### 프로즈 (3 문단)

베이스는 **(a) Attachment Protocol + 3그룹 분류**, **(b) 3그룹 병렬 수집 + null 필터 + `<system-reminder>` 자동 wrap**, **(c) assistant turn 카운터 / smoosh / 도구 풀 게이트 헬퍼**, **(d) 베이스 디폴트 어태치먼트 2종 (`date_change`, `todo_reminder`)** 만 제공한다. 30+ 종 도메인-특화 어태치먼트 본체는 Phase 7 + 도메인 책임 (PRD §5 OOS-1).

`RenderContext` 는 Phase 1 의 빈 모델 design intent 그대로 **어태치먼트가 읽는 슬롯 5개를 디폴트 값과 함께 추가** (`messages=()`, `todos=()`, `tool_pool=frozenset()`, `last_emit_date=None`, `is_subagent=False`) — 도메인이 안 채우면 디폴트 어태치먼트가 자동 스킵, Phase 1/2 backward compatible (R-6).

Phase 2 `LLMClient.generate(ctx)` Protocol 시그니처는 무변경 — 호출자가 명시적으로 helper `call_with_attachments(client, ctx, user_input)` 를 거쳐 어태치먼트 수집 + ctx.messages 합성 + LLM 호출을 1줄로 처리 (D3 β). 본격 ReAct 루프 통합은 Phase 5+ 가 helper 를 흡수.

## 2. 영향 받는 컴포넌트/파일

### 신규 (12 src + 13 test)

```
best_agent_base/
├── messages.py                                 # 신규: Message + ContentBlock (Pydantic frozen)
├── attachments/
│   ├── __init__.py                            # 신규: docstring-only (D-13)
│   ├── protocol.py                            # 신규: Attachment Protocol + AttachmentGroup StrEnum
│   ├── registry.py                            # 신규: AttachmentRegistry 싱글톤
│   ├── collect.py                             # 신규: collect_attachments + _wrap_system_reminder
│   ├── counter.py                             # 신규: count_turns_since 헬퍼
│   ├── smoosh.py                              # 신규: smoosh_into_last_tool_result 헬퍼
│   ├── gates.py                               # 신규: register_tool_pool_gate + 평가
│   ├── integrate.py                           # 신규: call_with_attachments helper (D3 β)
│   └── builtins/
│       ├── __init__.py                        # 신규: docstring-only (D-13)
│       ├── date_change.py                     # 신규: 자정 감지 (ALL_THREAD)
│       └── todo_reminder.py                   # 신규: 10 round 게이트 (ALL_THREAD)

tests/
├── test_attachments_protocol.py               # 신규
├── test_attachments_registry.py               # 신규
├── test_attachments_collect.py                # 신규
├── test_attachments_collect_timeout.py        # 신규
├── test_attachments_counter.py                # 신규
├── test_attachments_smoosh.py                 # 신규
├── test_attachments_gates.py                  # 신규
├── test_attachments_builtins_date.py          # 신규
├── test_attachments_builtins_todo.py          # 신규
├── test_attachments_init_purity.py            # 신규
├── test_attachments_static_hash_invariant.py  # 신규 (NFR-2)
├── test_attachments_ctx_slots.py              # 신규 (R-6 backward compat)
├── test_attachments_helper_integration.py     # 신규 (D3 β)
├── test_attachments_full_flow.py              # 신규 (mock LLMClient + builtins)
└── test_messages.py                           # 신규
```

### 변경 (2 src + 1 test 확장 + 1 conftest 확장)

```
best_agent_base/prompts/render.py              # 변경: RenderContext 슬롯 5개 추가
main.py                                        # 변경: helper 호출 데모 (선택)
tests/test_no_domain_vocab.py                  # 확장: grep 범위에 attachments/ + messages.py 추가
tests/conftest.py                              # 확장: restore_attachment_registry autouse fixture
```

### FR → 파일 매핑

| FR | 파일 |
|---|---|
| FR-1 (Attachment Protocol) | `attachments/protocol.py` |
| FR-2 (3그룹 enum) | `attachments/protocol.py` |
| FR-3 (병렬 수집 + null 필터 + wrap) | `attachments/collect.py` |
| FR-4 (이중 호출 시그니처) | `attachments/collect.py` |
| FR-5 (AttachmentRegistry) | `attachments/registry.py` |
| FR-6 (assistant turn 카운터) | `attachments/counter.py` |
| FR-7 (smoosh) | `attachments/smoosh.py` |
| FR-8 (베이스 디폴트 2종) | `attachments/builtins/date_change.py`, `attachments/builtins/todo_reminder.py` |
| FR-9 (도구 풀 게이트 슬롯) | `attachments/gates.py` |

## 3. 데이터 모델 / 스키마

### 3-1. 메시지 표현 (`best_agent_base/messages.py`)

```python
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
    content: str  # MVP: 문자열만. block list 는 후속 Phase

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

### 3-2. AttachmentGroup + Protocol (`attachments/protocol.py`)

```python
from enum import StrEnum
from typing import Protocol, runtime_checkable
from best_agent_base.prompts.render import RenderContext

class AttachmentGroup(StrEnum):
    USER_INPUT = "user_input"
    ALL_THREAD = "all_thread"
    MAIN_THREAD = "main_thread"

@runtime_checkable
class Attachment(Protocol):
    name: str
    group: AttachmentGroup
    async def build(self, ctx: RenderContext) -> str | None: ...
```

### 3-3. RenderContext 슬롯 추가 (`prompts/render.py` 변경)

```python
from datetime import date
from best_agent_base.messages import Message

class RenderContext(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # Phase 3 어태치먼트 슬롯 (모두 디폴트, R-6 backward compat)
    messages: tuple[Message, ...] = ()
    todos: tuple = ()                          # tuple[Any, ...] — 형식은 Phase 5+ (D6)
    tool_pool: frozenset[str] = frozenset()
    last_emit_date: date | None = None
    is_subagent: bool = False
```

### 3-4. 도구 풀 게이트 predicate

```python
# attachments/gates.py
from collections.abc import Callable

ToolPoolGate = Callable[[frozenset[str]], bool]
# True 반환 → 어태치먼트 스킵 (= 비활성)
# False 반환 → 어태치먼트 발화 (= 정상)
# 어태치먼트당 N개 게이트 등록 가능, 평가는 OR (true 1개 만나면 스킵, D7)
```

### 3-5. system-reminder wrap

CC `messages.ts:3098` 원본 그대로:

```python
def _wrap_system_reminder(text: str) -> str:
    return f"<system-reminder>\n{text}\n</system-reminder>"
```

## 4. 외부 인터페이스 (Public API)

### 4-1. attachments 모듈 import 표면

```python
from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry
from best_agent_base.attachments.collect import collect_attachments
from best_agent_base.attachments.counter import count_turns_since
from best_agent_base.attachments.smoosh import smoosh_into_last_tool_result
from best_agent_base.attachments.gates import register_tool_pool_gate
from best_agent_base.attachments.integrate import call_with_attachments

# Built-in 어태치먼트 — 모듈 import 시 자동 등록 (Phase 1 SectionRegistry 패턴 거울)
import best_agent_base.attachments.builtins.date_change      # auto-register
import best_agent_base.attachments.builtins.todo_reminder    # auto-register
```

### 4-2. 핵심 함수 시그니처

```python
async def collect_attachments(
    ctx: RenderContext,
    *,
    user_input: str | None,
) -> list[Message]:
    """3그룹 어태치먼트 병렬 수집 + null 필터 + <system-reminder> wrap.

    user_input=str  → USER_INPUT + ALL_THREAD + MAIN_THREAD 모두 호출 (user-turn entry)
    user_input=None → ALL_THREAD + MAIN_THREAD 만 호출 (in-loop, 도구 라운드 후)

    ctx.is_subagent=True 시 MAIN_THREAD 그룹 자동 제외 (원칙 #7)

    각 어태치먼트 build() 가 None → 자동 제외
    각 텍스트 → Message(role="user", content=(TextBlock("<system-reminder>...</system-reminder>"),))
    """

def count_turns_since(
    messages: tuple[Message, ...],
    predicate: Callable[[Message], bool],
) -> int: ...

def smoosh_into_last_tool_result(
    messages: tuple[Message, ...],
    reminder_text: str,
) -> tuple[Message, ...]: ...

def register_tool_pool_gate(
    attachment_name: str,
    predicate: Callable[[frozenset[str]], bool],
) -> None: ...

async def call_with_attachments(
    client: LLMClient,
    ctx: RenderContext,
    *,
    user_input: str,
    cache_policy: CachePolicy | None = None,
) -> LLMResponse:
    """user-turn entry helper. Phase 2 LLMClient 시그니처 무변경 (D3 β).

    flow: collect → ctx.messages 합성 → client.generate(new_ctx)
    """
```

### 4-3. AttachmentRegistry

```python
class AttachmentRegistry:
    def register(self, name: str, attachment: Attachment) -> None: ...
    def override(self, name: str, attachment: Attachment) -> None: ...  # alias
    def get(self, name: str) -> Attachment: ...
    def all_in_group(self, group: AttachmentGroup) -> Iterable[Attachment]: ...

attachment_registry = AttachmentRegistry()  # 모듈-레벨 싱글톤 (Phase 1 거울)
```

### 4-4. REST/이벤트

본 Phase 범위 밖. Phase 14 FastAPI 단계.

## 5. 핵심 결정 + 대안 비교 (10 결정)

### D1 — 아키텍처: RenderContext 확장 + 단일 ctx (B 채택)

**대안:** A) 별도 attachment_ctx / C) 별도 모듈 + 도메인이 ctx 확장

**채택 이유:** Phase 2 `generate(ctx)` 와 일관 + 베이스 디폴트 어태치먼트가 ctx 슬롯 직접 읽음 (외부 store 의존 X). Phase 1 빈 RenderContext 의 design intent 그대로 활용. C 의 "ctx 그대로" 는 베이스 디폴트 어태치먼트가 외부 store 인자 강제 → API 비대.

### D2 — 메시지 표현: 자체 Pydantic frozen 모델

**대안:** LangChain BaseMessage / 자체 dataclass

**채택 이유:** Phase 2 D1 에서 LangChain 제거함. dataclass 는 검증 없음. Pydantic frozen + discriminated union (`Annotated[Union[...], Field(discriminator="type")]`) 으로 타입 안전 + frozen invariant.

### D3 — Phase 2 통합: helper 함수 (β 채택)

**대안:** α) `LLMClient.generate(ctx, *, user_input)` 시그니처 확장 / γ) `ctx.user_input` 슬롯

**채택 이유:** Phase 2 LLMClient Protocol 무변경 (B-thin 보존, breaking change 없음). 호출 흐름 명시적. Phase 5 ReAct 루프가 helper 자연스럽게 흡수. α 는 Phase 2 Public API 깨짐 + 어태치먼트 안 쓰는 도메인도 user_input 강제. γ 는 frozen 모델 비효율 + ctx 의 "정적 vs in-flight" 경계 깨짐.

### D4 — `<system-reminder>` wrap 위치: collect_attachments 내부

**대안:** Attachment.build() 가 직접 wrap 텍스트 반환

**채택 이유:** 어태치먼트 작성자(도메인)가 wrap 형식 잊어먹어도 자동 보장. wrap 형식 통일성 (NFR-1 도메인 중립성과 일관). build() 는 raw text 만 반환 책임 — 의도 분리.

### D5 — 이중 호출: 단일 함수 + `user_input=None` 분기

**대안:** 두 함수 (`collect_for_user_turn` + `collect_in_loop`)

**채택 이유:** API 면 줄임. 함수 시그니처 1개로 통일 → 도메인이 외울 게 적음. CC 원본 `getAttachmentMessages(input, ...)` 도 동일 패턴.

### D6 — `todo_reminder` 의 todos 슬롯: `tuple[Any, ...]` (= `tuple` annotation)

**대안:** `tuple[dict, ...]` / 정식 `TodoItem` 타입 정의

**채택 이유:** TodoWrite 도구는 Phase 5+ OOS. 베이스는 형식 미정 슬롯만. 도메인이 `len(ctx.todos)` 만 보고 본문 안 박는 CC `messages.ts:3669` 패턴 그대로. Phase 5+ 에서 정식 타입 도입 시 슬롯 type 좁히기 (Phase 별 점진 강화).

### D7 — 도구 풀 게이트: predicate registry slot, 어태치먼트당 N개 게이트 OR 평가

**대안:** 어태치먼트당 1개 게이트만 / 어태치먼트 자체에 메서드 박기

**채택 이유:** 미래 확장성 (한 어태치먼트가 2+ 도구 풀 조건으로 비활성 — 예: SendUserMessage OR EmergencyAlert). predicate 등록 후 OR 평가 (true 1개 만나면 스킵). 어태치먼트 자체에 메서드 박으면 도메인 도구 이름이 베이스 코드로 새어들어옴 (NFR-1 위배).

### D8 — AttachmentRegistry: 모듈-레벨 싱글톤 (Phase 1 거울)

**대안:** ContextVar 기반 격리 / DI 컨테이너

**채택 이유:** Phase 1 SectionRegistry 와 동일 패턴 (베이스 일관성). 베이스 단계 = register 1회 → read-many 가정. 멀티-요청 격리는 Phase 14 FastAPI 시점 ContextVar 재검토 (R-1 deferred).

### D9 — 타임아웃: `asyncio.wait_for(gather, timeout=1.0)` + 개별 어태치먼트 try/except → None

**대안:** gather 자체 타임아웃 (`return_exceptions=True`) / 개별 어태치먼트 wait_for

**채택 이유:** 전체 1초 안에 정상 어태치먼트만 수확. 개별 어태치먼트 실패는 None → null 필터로 자동 스킵 → 전체 호출 죽지 않음 (NFR-3). CC 동작 동일.

### D10 — `is_subagent`: RenderContext boolean 슬롯 (디폴트 False)

**대안:** 별도 인자 (`collect_attachments(ctx, *, user_input, is_subagent)`) / 자동 감지

**채택 이유:** ctx 1개로 모든 컨텍스트 정보 통일 (D1 일관). 호출자(Phase 12 서브에이전트)가 ctx 만들 때 명시적으로 `is_subagent=True` 박음. MAIN_THREAD 그룹 제외 결정에 사용.

### Gemini CLI 비교 노트 (CLAUDE.md §2 룰)

- **Claude 우위 → 베이스 흡수**: `<system-reminder>` 자동 wrap + 3그룹 분류 + 이중 호출 지점 + smoosh = 베이스 메커니즘으로 박음
- **Claude 우위 → 베이스 흡수**: assistant turn 카운터 (thinking 제외) — 동급 메커니즘이 Gemini CLI 의 reminder 시스템에 부재

## 6. 위험 / 사이드이펙트 (preliminary, 8 리스크)

### R-1 (race) — `attachments/registry.py`

**설명:** `AttachmentRegistry.register()` 동시성 — 멀티-요청 환경에서 register/override 경쟁

**Mitigation:** Phase 1 R-1 거울 — register 1회 + read-many 가정 명시. Phase 14 FastAPI 시점 ContextVar 재검토 (D8 deferred).

### R-2 (race) — `attachments/collect.py`

**설명:** `asyncio.gather` 안 개별 어태치먼트 `build()` 가 공유 외부 store 접근 시 race

**Mitigation:** 베이스는 read-only ctx 가정. mutation 은 도메인 책임. ctx 가 frozen 모델이라 자체 race 없음.

### R-3 (side-effect) — `attachments/collect.py:_wrap_system_reminder`

**설명:** `<system-reminder>` 형식 깨짐 — 도메인이 build() 안에서 직접 wrap 시도 시 이중 wrap

**Mitigation:** D4 — 베이스가 wrap 책임. 도메인은 raw text 만 반환. 인터페이스 가이드 + Attachment.build docstring 명시.

### R-4 (side-effect) — `prompts/render.py:RenderContext`

**설명:** NFR-2 정적 캐시 안전 깨짐 — 누군가 어태치먼트를 BOUNDARY **위** 정적 7섹션 안으로 박음

**Mitigation:** 회귀 테스트 (어태치먼트 발화 전후 `get_static_hash` 동일). 베이스 collect_attachments 결과는 `ctx.messages` 에만 적재 (helper β 강제). 인터페이스 가이드 명시.

### R-5 (side-effect) — `attachments/smoosh.py`

**설명:** `tool_call_id` 누락 → Anthropic/Gemini SDK 에러

**Mitigation:** smoosh 함수가 `ToolResultBlock.tool_use_id` 추출 후 새 메시지에 보존. 단위 테스트로 검증.

### R-6 (breaking) — `prompts/render.py:RenderContext`

**설명:** RenderContext 신규 슬롯 5개 추가 — Phase 1/2 가 만든 RenderContext() 인스턴스 깨짐?

**Mitigation:** 모든 신규 필드 디폴트 값 보유 (`messages=()`, `todos=()`, `tool_pool=frozenset()`, `last_emit_date=None`, `is_subagent=False`) → 기존 코드 무변경 backward-compatible. 회귀 테스트 (Phase 1 70 + Phase 2 41) 모두 GREEN 검증.

### R-7 (perf) — `attachments/collect.py`

**설명:** 1초 타임아웃 시 정상 long-running 어태치먼트도 잘림 → 일부 데이터 누락

**Mitigation:** NFR-3 명시 — 어태치먼트 build() 는 sync read-only 가정 (CC 원칙 #2 "AI 호출 없이 이미 있는 정보만"). 1초 넘는 fetch 는 도메인 책임 (백그라운드 캐싱).

### R-8 (side-effect) — `attachments/counter.py`

**설명:** `count_turns_since` 가 thinking 메시지 식별 잘못 → todo_reminder 카운터 부정확 → 잘못된 시점 발화

**Mitigation:** `is_thinking_only(msg) = all(b.type == "thinking" for b in msg.content)` 명확 정의. 단위 테스트 (thinking 1+ 비-thinking 3 mixed 케이스).

## 7. 테스트 전략

### 7-1. 단위 테스트 (12 신규 + 1 확장)

| 파일 | 커버 | 비고 |
|---|---|---|
| `test_attachments_protocol.py` | AC-1, FR-1, FR-2 | Protocol/StrEnum 정의 검증, runtime_checkable |
| `test_attachments_registry.py` | AC-4, FR-5 | register/override/get/all_in_group, 모듈-레벨 싱글톤 |
| `test_attachments_collect.py` | AC-2, AC-3, FR-3, FR-4 | 3그룹 병렬 (mock 호출 횟수), null 필터, wrap, user_input=None 시 USER_INPUT 스킵, is_subagent=True 시 MAIN_THREAD 스킵 |
| `test_attachments_collect_timeout.py` | AC-11, NFR-3, R-7 | sleep(2) + 정상 N개 → 1초 안에 정상만 반환 |
| `test_attachments_counter.py` | AC-5, FR-6, R-8 | thinking-only 제외, predicate 만족 종료 |
| `test_attachments_smoosh.py` | AC-6, FR-7, R-5 | 마지막 tool_result 옆 합성, tool_call_id 보존, 도구 N개 시 마지막 1개 |
| `test_attachments_gates.py` | AC-8, FR-9 | 등록·평가, OR 합성 (D7) |
| `test_attachments_builtins_date.py` | AC-7 (date_change) | 자정 감지 mock — last_emit_date != today → 발화, 동일 → 스킵 |
| `test_attachments_builtins_todo.py` | AC-7 (todo_reminder) + 카운터 통합 | 9 round → 스킵, 10 round → 발화, 게이트 도구 풀 시 스킵 |
| `test_attachments_init_purity.py` | AC-12, NFR-4 | AST 검사 — `attachments/__init__.py` + builtins 본체 비어있음 |
| `test_messages.py` | D2 | Pydantic frozen 검증, discriminator, 잘못된 type 거부 |
| `test_attachments_helper_integration.py` | D3 (β helper) | call_with_attachments → mock LLMClient 에 합성 ctx 전달 |
| `test_no_domain_vocab.py` (확장) | NFR-1, AC-9 | grep 범위에 `attachments/` + `messages.py` 추가 |

### 7-2. invariant 테스트 (2 신규)

| 파일 | 커버 |
|---|---|
| `test_attachments_static_hash_invariant.py` | NFR-2, AC-10, R-4 — `get_static_hash` 동일 검증 (캐시 SDK 호출 없이 순수 구조) |
| `test_attachments_ctx_slots.py` | R-6 backward compat — RenderContext() 인자 0개 호출, 모든 신규 슬롯 디폴트, Phase 1/2 회귀 X |

### 7-3. 통합 테스트 (1 신규)

`test_attachments_full_flow.py` — mock GeminiClient + helper 호출 → date_change + todo_reminder 자동 발화 + ctx.messages 갱신 검증.

### 7-4. fixture 확장 (`tests/conftest.py`)

```python
@pytest.fixture(autouse=True)
def restore_attachment_registry():
    """attachment_registry snapshot/restore — 테스트 격리. Phase 2 패턴 거울."""
    from best_agent_base.attachments.registry import attachment_registry
    snapshot = dict(attachment_registry._attachments)
    try:
        yield
    finally:
        attachment_registry._attachments.clear()
        attachment_registry._attachments.update(snapshot)
```

### 7-5. ruff / mypy

- ruff: Phase 0~2 동일 룰 (line-length=100, py312, E/F/I)
- 신규 코드 ruff clean 검증 (Phase 2 Task 9 패턴)

### 7-6. 테스트 카운트 추정

- Phase 1: 70 → Phase 2: +41 → 111 → **Phase 3 예상: +35~50 → 146~161 tests**

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-10 21:00] [개발방향-수정]
- **id**: CH-20260510-001
- **이유**: 신규 기술 설계 (Phase 3 어태치먼트 시스템 — D1..D10 결정 + R-1..R-8 리스크 + 16 테스트 전략)
- **무엇이**: phase-3-attachments-tech-design.md 전체 (§1 아키텍처 + §2 영향파일 매핑 + §3 데이터 모델 + §4 외부 IF + §5 결정 + §6 리스크 + §7 테스트)
- **영향범위**: 없음 (최초 생성). PRD CH-20260508-001 의 FR-1..9 + NFR-1..4 + AC-1..12 모두 trace 완료 (verifying-spec PASS)
- **연관 항목**: CH-20260508-001 (PRD)
