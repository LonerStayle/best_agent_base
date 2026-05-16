# 요구사항: Phase 3 — 어태치먼트 시스템 (사용자 입력 + ReAct 라운드 양 지점)

> **For agentic workers:** This document is the PRD (planning-level only). NEXT STEP: invoke `designing-direction` skill (or run `/design`) to produce `phase-3-attachments-tech-design.md` from this document. Do NOT add tech decisions or implementation details here — those belong in the next two artifacts.

## 1. 배경/목적

Claude Code 분석(`/Users/goldenplanet/jinsup_space/CC/attachment-system.md`, `첨부시스템-이중설계와-TodoWrite-응용비법.md`)에서 확인된 핵심 발견 — **유저 메시지 텍스트 자체를 건드리지 않고, 별도 `<system-reminder>` 메시지로 30+ 종 정보를 자동 첨부**하는 메커니즘이 같은 모델로 일반 채팅보다 압도적 정확도를 만든다. "모델이 똑똑해서가 아니라, 모델에게 주는 맥락이 압도적으로 풍부해서."

본 Phase 는 이 메커니즘의 **베이스 골격**을 파이썬 백엔드로 포팅한다. 단, 30+ 종 어태치먼트 본체는 도메인마다 다르므로(코딩/의료/금융 등) 베이스에는 박지 않는다 — Phase 1 `SectionRegistry` / Phase 2 `LLMClient` 와 동일한 **"슬롯만 제공, 콘텐츠는 도메인 register"** 패턴.

추가로, 메커니즘이 실제로 작동함을 산출물 노트북에서 즉시 시연 가능하도록 **도메인-무관 베이스 디폴트 어태치먼트 2종** (`date_change`, `todo_reminder`) 만 베이스에 포함한다 — assistant turn 카운터·게이트·`<system-reminder>` wrap 모두 한 사례로 검증.

베이스 책임은 **메커니즘**(Protocol, 3그룹 분류, 병렬 수집, system-reminder wrap, 카운터, 이중 호출 시그니처, smoosh, 도구 풀 게이트 슬롯, 디폴트 어태치먼트 2종)이며 도메인-특화 어태치먼트(IDE 선택, LSP 진단, git diff, @file mention, MCP 리소스 등)는 본 Phase 범위 밖.

## 2. 사용자 스토리 / 시나리오

**시나리오 A — 도메인 에이전트 개발자 (메커니즘 활용 중심):**

> FastAPI 기반 의료 보조 에이전트를 만드는 개발자 K 는 "환자가 '저번 검사 결과는?' 이라고 물었을 때, 모델이 자동으로 최근 검사 데이터를 첨부받게" 하고 싶다.
> Phase 3 베이스가 `Attachment(Protocol)` + `register("patient_recent_lab", ...)` + 3그룹 분류만 제공하면, K 는 어태치먼트 1개 클래스만 구현하면 끝 — 카운터/병렬 수집/`<system-reminder>` wrap/이중 호출 지점 모두 자동.
> 결과: K 의 모델 호출은 도메인 어태치먼트 N개가 자동으로 user 메시지 뒤에 붙어 첫 응답부터 풍부한 컨텍스트로 답변.

**시나리오 B — 베이스 디폴트 어태치먼트 즉시 활용 (B 선택 강조):**

> A + "K 는 베이스 디폴트인 `date_change`/`todo_reminder` 가 자동으로 작동해서, 별도 구현 없이도 자정 넘을 때 '날짜 바뀜' + 모델이 `todos` 슬롯 갱신 없이 10 round 지나면 'todo 갱신 잊지 마' 가 자동 주입됨을 노트북에서 직접 검증."

## 3. 기능 요구사항 (FR)

- **FR-1: Attachment Protocol** — `Attachment(Protocol, runtime_checkable)` — `name: str`, `group: AttachmentGroup`, `async def build(ctx) -> str | None` 시그니처. 도메인이 자기 클래스에 베이스 import 없이도 register 가능 (Phase 1 PromptSection 패턴).
- **FR-2: 3그룹 분류 enum** — `AttachmentGroup(StrEnum)` 3 값:
  - `USER_INPUT` — 사용자 텍스트 의존, 입력 파싱 필요. in-loop 호출에서 스킵.
  - `ALL_THREAD` — 상태 기반, 메인·서브에이전트 모두 받음.
  - `MAIN_THREAD` — 상태 기반, 메인 대화에만 (서브에이전트 호출 시 자동 제외, 원칙 #7).
- **FR-3: 3그룹 병렬 수집 + null 필터 + system-reminder wrap** — `collect_attachments(ctx, *, user_input: str | None) -> list[Message]` 가 그룹별로 병렬 수집(전체 타임아웃 가짐)하고, `build()→None` 결과는 자동 제외, 각 결과 텍스트는 `<system-reminder>...</system-reminder>` 로 자동 wrap.
- **FR-4: 이중 호출 지점 시그니처** — 같은 함수의 두 모드:
  - `user_input=str` — user-turn entry (사용자 메시지 처리 시점). 3그룹 모두 호출.
  - `user_input=None` — in-loop (도구 라운드 후). USER_INPUT 그룹 스킵, ALL_THREAD + MAIN_THREAD 만 호출.
- **FR-5: AttachmentRegistry** — `register(name, attachment)` / `override(name, attachment)` 등록 API. 베이스 0줄 수정으로 도메인 확장 (Phase 1 SectionRegistry 패턴, 원칙 #8).
- **FR-6: assistant turn 카운터 헬퍼** — `count_turns_since(messages, predicate) -> int` — 메시지를 끝부터 거꾸로 훑으며 비-thinking assistant 메시지 단위로 카운트, predicate 만족 메시지 만나면 종료. thinking-only 메시지는 카운트에서 제외.
- **FR-7: smoosh 헬퍼** — `smoosh_into_last_tool_result(messages, reminder_text) -> messages` — in-loop 호출에서 reminder 를 마지막 user 메시지의 마지막 tool_result 옆 블록으로 합침. tool_result 가 없으면 별도 user 메시지로 append. `tool_call_id` 보존. provider strict alternation 대응.
- **FR-8: 베이스 디폴트 어태치먼트 2종** — `attachments/builtins/`:
  - `date_change` — `ALL_THREAD` 그룹. OS 시계 기반 자정 감지.
  - `todo_reminder` — `ALL_THREAD` 그룹. assistant turn 카운터 + N round 게이트 사용. `todos` 상태는 도메인이 슬롯으로 주입 (TodoWrite 도구 자체는 본 Phase 범위 밖, Phase 5+).
- **FR-9: 도구 풀 인지 게이트 슬롯** — `register_tool_pool_gate(attachment_name, predicate)` — 도구 풀 구성에 따라 특정 어태치먼트를 동적으로 끄는 등록 API. 실제 도구 이름은 도메인이 채움 (베이스 안 박지 않음). 베이스 디폴트 `todo_reminder` 가 게이트 호출 패턴 시연.

## 4. 비기능 요구사항 (NFR)

- **NFR-1: 도메인 중립성** — 베이스 코드/docstring 안에 도메인 어휘 박지 않음(코딩·의료·금융 등 모두 무관). regex grep 테스트(Phase 1 `test_no_domain_vocab.py` 패턴 그대로) — `auth/jwt/patient/wire_transfer/...` 키워드 0건.
- **NFR-2: 정적 캐시 안전 (구조적 invariant)** — 어태치먼트는 항상 Phase 1 BOUNDARY **아래**(동적부)에 들어가야 한다. 어태치먼트 N개 등록·발화 전후 `get_static_hash(ctx)` 동일. 캐시 SDK 호출 없이 순수 구조 테스트 — 캐시 활성/비활성/Phase 2 D6 fallback 모두 동일하게 보장.
- **NFR-3: 3그룹 병렬 수집 타임아웃** — 전체 타임아웃 1초 (CC 동일). 개별 어태치먼트 timeout 시 `None` 반환 → null 필터로 자동 스킵 → 전체 호출 죽지 않음.
- **NFR-4: `__init__.py` docstring-only (D-13)** — `attachments/__init__.py` 본체에 import/대입/함수 정의 없음. AST 테스트.

## 5. 범위 밖 (Out of Scope)

1. **실제 어태치먼트 종류 (도메인 의존)** — `@file mention`, `lsp_diagnostics`, `ide_selection`, `changed_files`, `nested_memory`, `mcp_resources` 등 30+ 종 → Phase 7 (유저 질문 어태치먼트) + 도메인 책임.
2. **도구 풀 인지 게이트의 실제 도구 이름** — FR-9 는 predicate 등록 슬롯만. `SendUserMessage` 같은 구체 도구 이름은 Phase 5+ (도구 베이스) + 도메인이 채움.
3. **성능 수치 (p95 < Nms 등)** — 어태치먼트 종류·도메인마다 다양 → 도메인 책임.
4. **입력 검증 / 보안** — `@db:table.row_id` 같은 권한 검사·마스킹 → Phase 7.
5. **`compaction_reminder` 같은 토큰/컨텍스트 의존 어태치먼트** — 토큰 측정 메트릭이 Phase 9+ 라 베이스 디폴트 후보에서 제외.
6. **`auto_mode` / `plan_mode` 같은 모드 어태치먼트** — 모드 시스템(Phase 후순위) 의존.
7. **MCP 리소스 멘션 어태치먼트** — Phase 6 (MCP 어댑터) 이후.
8. **TodoWrite 도구 자체** — `todo_reminder` 어태치먼트는 베이스 디폴트지만 TodoWrite 도구는 Phase 5+. 베이스의 `todo_reminder` 는 `todos: list` 슬롯 주입식.

## 6. 수용 기준 (Acceptance Criteria)

- **AC-1**: `Attachment(Protocol, runtime_checkable)` 정의 + 3그룹 `AttachmentGroup(StrEnum)` 3 값 (`USER_INPUT`/`ALL_THREAD`/`MAIN_THREAD`) 존재 검증. (FR-1, FR-2)
- **AC-2**: `collect_attachments(ctx, user_input="hi")` 호출 시 3그룹 어태치먼트가 병렬 수집되고, 각 결과는 `<system-reminder>...</system-reminder>` 로 자동 wrap, `build()→None` 반환은 결과 list 에서 자동 제외. (FR-3)
- **AC-3**: `user_input=None` 호출 시 USER_INPUT 그룹 어태치먼트는 호출되지 않고 ALL_THREAD + MAIN_THREAD 만 호출됨 (mock 으로 호출 횟수 검증). (FR-4)
- **AC-4**: `attachment_registry.register("foo", FakeAttachment())` 후 `collect_attachments` 결과에 포함, `override("foo", OtherAttachment())` 시 새 구현으로 대체. 베이스 코드 0줄 수정. (FR-5)
- **AC-5**: `count_turns_since(messages, predicate)` 가 thinking-only assistant 메시지를 카운트에서 제외함 (thinking 1개 + 비-thinking 3개 + predicate 만족 메시지 → 카운트 = 3). (FR-6)
- **AC-6**: `smoosh_into_last_tool_result(messages, reminder)` — 마지막 user 메시지가 tool_result 가지면 같은 메시지 content 끝에 reminder 블록 append. 없으면 별도 user 메시지로 추가. tool_call_id 보존 검증. (FR-7)
- **AC-7**: 베이스 디폴트 어태치먼트 2종이 `attachments/builtins/` 에 존재: `date_change` (자정 감지 mock 으로 발화 검증), `todo_reminder` (assistant turn 10 round 게이트 검증). (FR-8)
- **AC-8**: `register_tool_pool_gate("todo_reminder", lambda tools: "X" in tools)` 등록 후, 도구 풀에 X 있으면 `todo_reminder` 스킵, 없으면 발화. (FR-9)
- **AC-9**: `tests/test_no_domain_vocab.py` regex grep — 베이스 코드/docstring 안 도메인 키워드(auth/jwt/patient/wire_transfer/...) 0건. (NFR-1)
- **AC-10**: 어태치먼트 N개 등록 + 발화 전후 `get_static_hash(ctx)` 동일. 캐시 SDK 호출 없이 순수 구조 테스트. (NFR-2)
- **AC-11**: `asyncio.sleep(2)` 어태치먼트 1개 + 정상 어태치먼트 N개 → `collect_attachments` 1초 안에 정상만 반환, 죽은 1개는 null 필터로 자동 스킵 (전체 호출 죽지 않음). (NFR-3)
- **AC-12**: AST 테스트 — `attachments/__init__.py` 본체에 import/대입/함수 정의 없음 (docstring-only, D-13). (NFR-4)

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-08 21:00] [요구사항-수정]
- **id**: CH-20260508-001
- **이유**: 신규 피처 brainstorming 결과 (Phase 3 — 어태치먼트 시스템 + 베이스 디폴트 어태치먼트 2종)
- **무엇이**: phase-3-attachments-requirements.md 전체 (FR-1..9, NFR-1..4, AC-1..12, OOS 8항목)
- **영향범위**: 없음 (최초 생성)
