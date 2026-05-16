# 어태치먼트 시스템 — 인터페이스 가이드

## 1. 모듈 책임

**Claude Code 의 30+ 종 자동 첨부 메커니즘을 베이스 골격으로 포팅 — Protocol + 3그룹 분류 + 병렬 수집 + `<system-reminder>` 자동 wrap + assistant turn 카운터 + smoosh + 도구 풀 게이트 슬롯 + 베이스 디폴트 어태치먼트 2종 (`date_change`, `todo_reminder`) + LLM 호출 helper β**.

도메인-특화 어태치먼트 본체 (IDE 선택 / LSP 진단 / git diff / @file mention / MCP 리소스 등 30+ 종) 는 도메인 책임 — 베이스는 메커니즘 슬롯만 제공.

핵심 invariant 두 가지:
1. **NFR-2 정적 캐시 안전**: 어태치먼트는 항상 시스템 프롬프트 BOUNDARY **아래** (동적부) 에만 적재 → 정적 7섹션 해시 변동 0 → LLM 클라이언트 통합 (캐싱 흡수) 의 KV 캐시 유지
2. **NFR-1 도메인 중립성**: 베이스 코드/docstring 안에 도메인 어휘 박지 않음 (의료/금융/코딩 등 모두 무관)

---

## 2. 사용 예시

### 2.1 가장 단순한 호출 — helper β 1줄

```python
import asyncio
from best_agent_base.attachments.builtins import date_change, todo_reminder  # auto-register
from best_agent_base.attachments.integrate import call_with_attachments
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.render import RenderContext


async def main():
    client = GeminiClient()
    ctx = RenderContext()
    resp = await call_with_attachments(client, ctx, user_input="hello")
    print(resp.text)


asyncio.run(main())
```

helper 가 내부에서 자동으로:
1. `collect_attachments(ctx, user_input="hello")` — 3그룹 어태치먼트 병렬 수집 + null 필터 + `<system-reminder>` wrap
2. `ctx.messages` 에 사용자 입력 메시지 + 어태치먼트 메시지 합성 (frozen ctx → `model_copy`)
3. `client.generate(new_ctx)` — Phase 2 LLMClient Protocol 시그니처 무변경

### 2.2 베이스 디폴트 어태치먼트 즉시 시연

```python
from datetime import date, timedelta

# date_change: last_emit_date 가 오늘과 다르면 발화
yesterday = date.today() - timedelta(days=1)
ctx_date = RenderContext(last_emit_date=yesterday)
resp = await call_with_attachments(client, ctx_date, user_input="안녕")
# → ctx.messages 안에 "<system-reminder>The date has changed. Today's date is now ...</system-reminder>" 자동 주입

# todo_reminder: 마지막 TodoWrite 호출 이후 10 round 지나면 발화
from best_agent_base.messages import Message, TextBlock
msgs = tuple(
    Message(role="assistant", content=(TextBlock(text=f"r{i}"),)) for i in range(10)
)
ctx_todo = RenderContext(messages=msgs)
resp = await call_with_attachments(client, ctx_todo, user_input="진행해")
# → "<system-reminder>The TodoWrite tool hasn't been used recently...</system-reminder>" 자동 주입
```

### 2.3 도메인 어태치먼트 등록 — 베이스 0줄 수정 (Open/Closed)

```python
from best_agent_base.attachments.protocol import Attachment, AttachmentGroup
from best_agent_base.attachments.registry import attachment_registry


class _MyContextAttachment:
    """도메인이 자기 ctx 에서 정보 추출해 어태치먼트로 변환."""

    name = "my_recent_state"
    group = AttachmentGroup.ALL_THREAD

    async def build(self, ctx) -> str | None:
        recent = getattr(ctx, "recent_state", None)
        if not recent:
            return None  # 조건부 생성 — 베이스가 자동 스킵
        return f"Recent state snapshot:\n{recent}"


attachment_registry.register("my_recent_state", _MyContextAttachment())
# 이후 모든 call_with_attachments / collect_attachments 호출에 자동 흡수
```

### 2.4 도구 풀 인지 게이트 — 도메인 도구 이름 등록

```python
from best_agent_base.attachments.gates import register_tool_pool_gate

# 도메인 도구 풀에 "EmergencyAlert" 가 있으면 todo_reminder 자동 비활성
register_tool_pool_gate(
    "todo_reminder",
    lambda tools: "EmergencyAlert" in tools,
)

# 같은 어태치먼트에 N개 게이트 등록 가능 — OR 평가 (1개라도 True → 스킵)
register_tool_pool_gate(
    "todo_reminder",
    lambda tools: "MaintenanceMode" in tools,
)
```

베이스 코드에는 도구 이름 박지 않음 (NFR-1) — 도메인이 predicate 안에 채움.

### 2.5 ReAct in-loop 호출 (도구 라운드 후) — `user_input=None`

```python
from best_agent_base.attachments.collect import collect_attachments

# 도구 호출 후, 같은 함수 재호출 — USER_INPUT 그룹 자동 스킵
in_loop_msgs = await collect_attachments(ctx, user_input=None)
# → ALL_THREAD + MAIN_THREAD 만 호출 (USER_INPUT 은 사용자 텍스트 의존이라 스킵)
```

### 2.6 in-loop reminder 합성 — smoosh

```python
from best_agent_base.attachments.smoosh import smoosh_into_last_tool_result

# 도구 결과 메시지 + reminder 를 같은 user 메시지 안에 두 블록으로 합성
# (Gemini strict alternation + Anthropic 호환)
new_messages = smoosh_into_last_tool_result(
    ctx.messages,
    "<system-reminder>todo 갱신 잊지 마</system-reminder>",
)
# 마지막 user 메시지가 tool_result 가지면 같은 메시지에 TextBlock append
# 없으면 별도 user 메시지로 추가
# tool_call_id 보존 (frozen 모델 + 새 메시지 재생성)
```

### 2.7 서브에이전트 컨텍스트 격리

```python
# 서브에이전트 호출 시 MAIN_THREAD 그룹 자동 제외 (원칙 #7 격리된 컨텍스트)
sub_ctx = RenderContext(is_subagent=True)
sub_msgs = await collect_attachments(sub_ctx, user_input="search foo")
# → USER_INPUT + ALL_THREAD 만, MAIN_THREAD 어태치먼트는 호출 안 됨
```

---

## 3. 핵심 개념

### 3.1 3그룹 분류 (CC `attachment-system.md`)

| 그룹 | 트리거 | 서브에이전트도 받음? | 대표 (도메인) |
|---|---|---|---|
| `USER_INPUT` | 사용자 텍스트 의존 (입력 파싱 필요) | ✅ Yes | `@file` mention, MCP 리소스 mention, agent mention, skill discovery |
| `ALL_THREAD` | 상태 기반 (입력 무관) | ✅ Yes | `date_change` ✓, `todo_reminder` ✓, git diff, 메모리 파일, deferred 도구 변경 |
| `MAIN_THREAD` | 상태 기반, 메인 대화 전용 | ❌ No (서브에이전트 격리) | IDE 선택, IDE 열린 파일, LSP 진단, 토큰 사용량 |

**`✓` = 베이스 디폴트 포함.** 나머지는 도메인 책임.

### 3.2 이중 호출 지점 (CC `첨부시스템-이중설계와-TodoWrite-응용비법.md`)

| 호출 지점 | 시그니처 | 그룹 호출 |
|---|---|---|
| **user-turn entry** (사용자 메시지 처리 시점) | `collect_attachments(ctx, user_input="...")` | USER_INPUT + ALL_THREAD + MAIN_THREAD 모두 |
| **in-loop** (ReAct 도구 라운드 후) | `collect_attachments(ctx, user_input=None)` | ALL_THREAD + MAIN_THREAD 만 (USER_INPUT 스킵) |

`is_subagent=True` 시 두 케이스 모두 MAIN_THREAD 자동 제외.

### 3.3 메시지 흐름

```
도메인 → call_with_attachments(client, ctx, user_input)
            │
            ▼
         collect_attachments(ctx, user_input=...)
            │
        asyncio.wait(timeout=1.0, ALL_COMPLETED)
            │
   ┌────────┼────────┬──────────┐
   ▼        ▼        ▼          ▼
USER_INPUT ALL_THREAD MAIN_THREAD
   │        │        │
   ▼        ▼        ▼
 build()  build()  build()  → None 자동 제외 + <system-reminder> wrap
            │
            ▼
list[Message(role="user", content=(TextBlock("<system-reminder>..."),))]
            │
            ▼
ctx.model_copy(update={"messages": prior + user_msg + attachments})
            │
            ▼
client.generate(new_ctx)  ← Phase 2 LLMClient 시그니처 무변경
            │
            ▼
        Gemini / Anthropic 어댑터 — split_at_boundary() 정적/동적 분리 → 정적은 캐시
```

### 3.4 system-reminder wrap 형식 (CC `messages.ts:3098`)

```
<system-reminder>
{어태치먼트 raw text}
</system-reminder>
```

베이스가 wrap 책임 (도메인 build() 는 raw text 만 반환) — 형식 통일성 보장.

### 3.5 NFR-2 정적 캐시 안전 invariant

어태치먼트는 항상 `ctx.messages` 에만 적재 → 시스템 프롬프트 BOUNDARY 위 정적 7섹션은 무변경 → `get_static_hash(ctx)` 동일 → LLM 클라이언트 통합 의 캐싱 자동 작동.

`call_with_attachments` helper 가 이 invariant 를 코드 레벨로 강제 (Phase 2 와 기계적 호환).

---

## 4. 확장 포인트

### 4.1 도메인 어태치먼트 등록 (`AttachmentRegistry`)

`Attachment(Protocol)` 만족하는 클래스 만들고 `attachment_registry.register(name, instance)`. 베이스 0줄 수정. `override(name, instance)` 로 베이스 디폴트 교체 가능.

### 4.2 ctx 슬롯 추가

`RenderContext` 는 빈 모델 design intent — 도메인이 필드 추가:

```python
from best_agent_base.prompts.render import RenderContext

class MyDomainCtx(RenderContext):
    user_id: str
    recent_actions: tuple = ()
    domain_state: dict | None = None
```

도메인 어태치먼트 `build(self, ctx)` 안에서 `ctx.recent_actions` 등 직접 읽음.

### 4.3 도구 풀 게이트 (FR-9)

`register_tool_pool_gate(attachment_name, predicate)` — 어태치먼트당 N개 게이트 OR 평가. 도메인 도구 이름은 베이스에 박지 않음.

### 4.4 카운터 헬퍼 (`count_turns_since`)

도메인 어태치먼트가 reminder 디바운스 / N round 게이트 등 카운터 로직 필요 시 그대로 재사용:

```python
from best_agent_base.attachments.counter import count_turns_since

turns = count_turns_since(
    ctx.messages,
    lambda m: m.role == "assistant" and ...some predicate...,
)
if turns >= MY_THRESHOLD:
    return "발화 텍스트"
```

`thinking-only` assistant 메시지는 자동 제외 (R-8 mitigation).

### 4.5 in-loop smoosh 헬퍼

ReAct 루프 in-loop reminder 가 도구 결과 메시지에 깔끔히 합쳐지도록 — `smoosh_into_last_tool_result(messages, reminder_text)`. provider strict alternation 대응.

---

## 5. 위험

| 카테고리 | 위치 | 위험 | mitigation |
|---|---|---|---|
| **race** | `attachments/registry.py` | register/override 멀티-요청 동시성 | register 1회 + read-many 가정. ContextVar 격리는 FastAPI 단계 재검토 |
| **race** | `attachments/collect.py` | `gather` 안 build() 가 외부 store mutation 시 race | ctx frozen + read-only 가정. mutation 은 도메인 책임 |
| **side-effect** | `attachments/collect.py:_wrap_system_reminder` | 도메인이 build() 안 직접 wrap 시 이중 wrap | 베이스가 wrap 책임 (D4) — 도메인은 raw text 만 반환 |
| **side-effect** | `prompts/render.py:RenderContext` | 어태치먼트가 BOUNDARY 위 정적부로 새어들어감 | `tests/test_attachments_static_hash_invariant.py` 회귀. helper β 가 ctx.messages 만 적재 |
| **side-effect** | `attachments/smoosh.py` | tool_call_id 누락 → SDK 에러 | ToolResultBlock 객체 frozen 보존 (새 메시지 재구성), 단위 테스트 |
| **breaking** | `prompts/render.py:RenderContext` | 신규 슬롯 5개 추가가 기존 `RenderContext()` 호출 깨뜨림 | 모든 신규 필드 디폴트 값 (`messages=()`, `todos=()`, `tool_pool=frozenset()`, `last_emit_date=None`, `is_subagent=False`) — 0건 회귀 |
| **perf** | `attachments/collect.py` | 1초 타임아웃 시 long-running 어태치먼트 잘림 | 의도된 trade-off. build() 는 sync read-only 가정 (CC 원칙 "AI 호출 없이 이미 있는 정보만"). 1초 넘는 fetch 는 도메인 백그라운드 캐싱 |
| **side-effect** | `attachments/counter.py` | thinking 식별 잘못 → 카운터 부정확 | `_is_thinking_only` = `all(b.type == "thinking" for b in msg.content)` 명확 정의, 단위 테스트 (thinking 1+ 비-thinking 3 mixed) |

---

## 6. 다른 모듈 연계

- **시스템 프롬프트 7섹션 골격 (정적/동적 분리)** — `RenderContext` 가 슬롯 컨테이너. 어태치먼트 슬롯 5개는 모두 동적부 (BOUNDARY 아래) 에만 영향 → 정적부 캐시 invariant 자동 보존
- **LLM 클라이언트 통합 (캐싱 흡수)** — `LLMClient` Protocol 시그니처 무변경. `call_with_attachments` helper 가 새 `RenderContext` 만들어 `client.generate(new_ctx)` 호출. 정적부 변동 없음 → KV 캐시 유지
- **ReAct 루프 + 흐름 기반 도구 컨트롤 (후속)** — 본격 in-loop 호출 통합은 ReAct 루프가 helper 흡수. 본 모듈은 메커니즘 슬롯만 제공
- **유저 질문 어태치먼트 (후속)** — `@file` mention 등 30+ 종 도메인-특화 어태치먼트는 후속 단계 + 도메인 책임. 본 모듈의 Protocol + Registry + 3그룹 매핑 그대로 활용
- **도구 베이스 (후속)** — 실제 도구 이름 ("SendUserMessage" 등) 은 후속 단계 부터 등장. `register_tool_pool_gate(...)` 슬롯에 도메인이 채움
- **유연한 HITL (후속)** — `MAIN_THREAD` 그룹 + `is_subagent` 플래그가 격리 메커니즘 제공
- **휴먼 인 더 루프 / 컨텍스트 관리 (후속)** — `count_turns_since` + `smoosh_into_last_tool_result` 가 reminder 디바운스 + 결과 합성 헬퍼로 재사용

---

## 7. 데모 노트북

- 위치: `notebooks/phase-3-attachments-demo.ipynb`
- 4부 골격 (산출물 룰):
  - **Setup**: import + `attachment_registry` snapshot fixture (대화형 격리)
  - **1부 베이스**: 빈 ctx 호출 + 베이스 디폴트 (`date_change`, `todo_reminder`) 즉시 시연
  - **2부 register/override**: 도메인 `Attachment` 정의 + `register("my_x", ...)` + 결과 확인 + `override("date_change", ...)` 로 베이스 디폴트 교체
  - **3부 escape hatch + 위험 가드**: 도구 풀 게이트 / `is_subagent=True` MAIN_THREAD 격리 / 1초 timeout 동작 확인 (`asyncio.sleep(2.0)` 어태치먼트)
  - **cleanup**: `restore` fixture
  - **다른 모듈 연계**: `call_with_attachments` + Phase 2 mock LLMClient → 합성된 `ctx.messages` 확인 + `get_static_hash` 동일 (NFR-2 invariant 시연)
  - **실습 4개**: (a) 도메인 어태치먼트 1개 만들기, (b) 도구 풀 게이트로 disable, (c) `count_turns_since` 헬퍼로 자기 카운터 어태치먼트, (d) `smoosh` 활용한 in-loop reminder

---

## 8. Public API

```python
# 모델 (best_agent_base/messages.py)
Message              # role: Literal["user","assistant"], content: tuple[ContentBlock, ...]
ContentBlock         # Annotated[Union[TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock], discriminator="type"]
TextBlock            # type="text", text: str
ToolUseBlock         # type="tool_use", id, name, input
ToolResultBlock      # type="tool_result", tool_use_id, content
ThinkingBlock        # type="thinking", text

# Protocol + Enum (best_agent_base/attachments/protocol.py)
Attachment           # Protocol(runtime_checkable) — name, group, async build(ctx) -> str | None
AttachmentGroup     # StrEnum — USER_INPUT / ALL_THREAD / MAIN_THREAD

# Registry (best_agent_base/attachments/registry.py)
AttachmentRegistry   # 클래스
attachment_registry  # 모듈-레벨 싱글톤
attachment_registry.register(name, attachment)
attachment_registry.override(name, attachment)
attachment_registry.get(name) -> Attachment
attachment_registry.all_in_group(group) -> Iterable[Attachment]

# 핵심 함수 (best_agent_base/attachments/collect.py)
async collect_attachments(ctx, *, user_input: str | None) -> list[Message]
COLLECT_TIMEOUT_SECONDS = 1.0

# 헬퍼 (best_agent_base/attachments/{counter,smoosh,gates,integrate}.py)
count_turns_since(messages, predicate) -> int
smoosh_into_last_tool_result(messages, reminder_text) -> tuple[Message, ...]
register_tool_pool_gate(attachment_name, predicate) -> None
ToolPoolGate          # type alias = Callable[[frozenset[str]], bool]
async call_with_attachments(client, ctx, *, user_input, cache_policy=None) -> LLMResponse

# 베이스 디폴트 어태치먼트 (best_agent_base/attachments/builtins/)
date_change.date_change_attachment            # 자정 감지, ALL_THREAD
todo_reminder.todo_reminder_attachment        # 10 round 게이트, ALL_THREAD
todo_reminder.TODO_REMINDER_THRESHOLD = 10

# RenderContext 신규 슬롯 (best_agent_base/prompts/render.py — 본 단계에서 추가)
ctx.messages: tuple[Message, ...] = ()
ctx.todos: tuple = ()                # tuple[Any, ...] — 정식 타입은 후속 단계
ctx.tool_pool: frozenset[str] = frozenset()
ctx.last_emit_date: date | None = None
ctx.is_subagent: bool = False
```
