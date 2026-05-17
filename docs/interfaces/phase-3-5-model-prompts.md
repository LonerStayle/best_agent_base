# 모델별 프롬프트 변형 슬롯 — 인터페이스 가이드

## 1. 모듈 책임

**CC `getAntModelOverrideSection` 백엔드 포팅 — 같은 시스템 프롬프트 / 도구 description 안에서 모델 별로 다른 변형을 박을 수 있는 슬롯**. 도메인 에이전트가 Claude 모델용 / Gemini 모델용 텍스트를 한 곳에 박고, 어댑터가 자기 model 이름 자동 주입 → 매칭 안 되는 블록 자동 strip.

핵심 invariant 두 가지:
1. **NFR-2 backward compat** — 마커 안 박힌 코드 = 모든 모델에서 동일 출력 (조용한 정규화 D2). `RenderContext()` 무인자 호출 가능.
2. **NFR-3 정적 캐시 안전** — 같은 모델 호출 시 동일 hash (캐시 적중 유지), 다른 모델 호출 시 다른 hash (모델별 독립 캐시).

---

## 2. 사용 예시

### 2.1 가장 단순한 사용 — 도메인이 마커 박고 어댑터 자동 주입

```python
from best_agent_base.llm.gemini import GeminiClient
from best_agent_base.prompts.registry import registry
from best_agent_base.prompts.render import RenderContext


class _MyDoingTasks:
    """Phase 1 DoingTasks 섹션 override — 모델별 변형 박음."""
    name = "DoingTasks"
    static = True

    def render(self, ctx):
        return (
            "Always think step-by-step.\n"
            "@[MODEL: claude-*]Use <thinking> tags for internal reasoning.@[/MODEL]"
            "@[MODEL: gemini-*]Use markdown ## headings for reasoning.@[/MODEL]"
        )


registry.override("DoingTasks", _MyDoingTasks())

client = GeminiClient()  # 자기 model 이름 자동 주입
resp = await client.generate(RenderContext())  # ctx.model=None → "gemini-2.5-flash" 주입
# → 정적 7섹션 안에서 @[MODEL: gemini-*] 블록만 keep, claude-* strip
```

### 2.2 명시적 model 지정

```python
ctx = RenderContext(model="claude-sonnet-4-5-20250929")
resp = await client.generate(ctx)  # 어댑터 자동 주입 우회 (도메인 우선)
```

### 2.3 두 어댑터 동일 코드, 다른 prompt 자동 분기

```python
from best_agent_base.llm.anthropic import AnthropicClient

gem = GeminiClient()
anth = AnthropicClient()

# 같은 ctx, 같은 호출 — 어댑터가 자기 model 이름으로 분기
await gem.generate(ctx)   # _MyDoingTasks 의 gemini-* 블록만 통과
await anth.generate(ctx)  # claude-* 블록만 통과
```

### 2.4 일반 helper 단독 사용

```python
from best_agent_base.prompts.model_filter import filter_model_blocks

text = "공통 @[MODEL: claude-*]<thinking>X</thinking>@[/MODEL] 끝"
filter_model_blocks(text, "claude-sonnet-4-5-20250929")  # → "공통 <thinking>X</thinking> 끝"
filter_model_blocks(text, "gemini-2.5-flash")            # → "공통  끝"
filter_model_blocks(text, None)                          # → "공통  끝" (모든 마커 strip)
```

### 2.5 glob 패턴 정밀 매칭

```python
text = "@[MODEL: claude-sonnet-4-*]sonnet-4 특화@[/MODEL]@[MODEL: claude-opus-*]opus 특화@[/MODEL]"
filter_model_blocks(text, "claude-sonnet-4-5-20250929")  # → "sonnet-4 특화"
filter_model_blocks(text, "claude-opus-4-7")             # → "opus 특화"
filter_model_blocks(text, "gemini-2.5-flash")            # → ""
```

### 2.6 도메인 catalog 별도 정의

```python
# 도메인은 자기 모델 이름 사전 정의 (베이스에는 박지 않음 — NFR-1)
DOMAIN_MODELS = {
    "claude_main": "claude-sonnet-4-5-20250929",
    "gemini_fast": "gemini-2.5-flash",
    "internal_vllm": "my-internal-vllm-1b",
}
ctx = RenderContext(model=DOMAIN_MODELS["claude_main"])
```

### 2.7 모델별 prompt + 어태치먼트 통합 (Phase 3 helper)

```python
from best_agent_base.attachments.integrate import call_with_attachments

# Phase 3 helper 도 ctx.model 그대로 전달 — 어태치먼트 build() 안에서도 ctx.model 활용 가능
ctx = RenderContext(model="claude-sonnet-4-5-20250929")
resp = await call_with_attachments(client, ctx, user_input="hi")
```

---

## 3. 핵심 개념

### 3.1 마커 문법

```
@[MODEL: <fnmatch pattern>]<inner content>@[/MODEL]
```

- `<pattern>`: fnmatch glob — `claude-*` / `gemini-*` / `claude-sonnet-4-*` / `*`
- `<inner content>`: 매칭 모델일 때 keep, 미매칭 시 전체 (마커 라인 포함) strip
- 단일 레벨 — 중첩 (`@[MODEL: a]@[MODEL: b]X@[/MODEL]@[/MODEL]`) 은 `ValueError`

### 3.2 filter 동작 표

| ctx.model | 마커 패턴 | 동작 |
|---|---|---|
| `"claude-sonnet-4-5-20250929"` | `@[MODEL: claude-*]X@[/MODEL]` | X keep |
| `"gemini-2.5-flash"` | `@[MODEL: claude-*]X@[/MODEL]` | 전체 strip |
| `None` | `@[MODEL: *]X@[/MODEL]` | 전체 strip (조용한 정규화) |
| 모든 값 | 마커 없는 텍스트 | 그대로 |

### 3.3 hash 격리 흐름

```
RenderContext(model="claude-sonnet-...")  ──┐
                                            ├─→ _render_static + filter_model_blocks 적용
RenderContext(model="gemini-2.5-flash")  ──┘
                                            │
                                            ▼
                              filter 적용 후 텍스트 hash
                                            │
                                            ▼
                       모델별로 다른 sha256 → Phase 2 KV 캐시 격리
```

### 3.4 어댑터 자동 주입 우선순위

```
ctx.model is None?
    │
    ├─ Yes → 어댑터가 자기 model 이름 주입 (Gemini: self._profile.model.value / Anthropic: self._model)
    │
    └─ No  → 도메인 명시 model 그대로 사용 (override)
```

### 3.5 Phase 1/2 와의 통합

- **Phase 1 BOUNDARY 마커 + Phase 3.5 filter** — 정적부 (BOUNDARY 위 7섹션) 와 동적부 (BOUNDARY 아래) **양쪽 모두** filter 적용. 정적부 hash 변동 = 모델 변경 시만.
- **Phase 2 LLMClient Protocol 시그니처 무변경** — `generate(ctx, *, cache_policy)` 그대로. helper / filter 는 내부 처리.

---

## 4. 확장 포인트

### 4.1 도메인 PromptSection 안에 마커 박기

`Section.render(ctx)` 결과 안에 `@[MODEL: pattern]...@[/MODEL]` 자유 배치. 베이스가 자동으로 필터링.

### 4.2 도메인 모델 이름 정의

베이스에는 모델 이름 박지 않음 (NFR-1). 도메인이 자기 catalog (StrEnum / dict / Pydantic Settings) 로 정의.

### 4.3 filter_model_blocks 단독 사용

PromptSection 외 다른 곳 (도구 description, 어태치먼트 build 결과 등) 에서도 같은 helper 재사용. Phase 4+ 도구 베이스에서 description 모델별 변형에 그대로 활용.

### 4.4 어댑터 model 자동 주입 우회

도메인이 명시적으로 `RenderContext(model="my-custom-model")` 박으면 어댑터가 그대로 사용. "_disabled" 같은 sentinel 박아서 자동 주입을 막는 패턴은 OOS — 필요하면 도메인이 구현.

---

## 5. 위험

| 카테고리 | 위치 | 위험 | mitigation |
|---|---|---|---|
| **side-effect** | `model_filter.py:_MARKER_RE` | greedy 매칭으로 2 연속 블록 잘못 합침 | `(.*?)` non-greedy + `re.DOTALL`. 단위 테스트 `test_two_consecutive_blocks_non_greedy` |
| **side-effect** | `prompts/render.py:get_static_hash` | 같은 ctx 반복 호출 시 다른 hash 가 나오면 캐시 미스 폭발 | 어댑터 자동 주입으로 None fallback 케이스 최소화. 회귀 `test_hash_stable_same_model_repeated` |
| **breaking** | `prompts/render.py:RenderContext` | 슬롯 추가가 Phase 1~3 호출 (11+ 사이트) 깸 | 디폴트 None + Phase 1~3 회귀 187 GREEN 검증 |
| **perf** | `model_filter.py` | 매 render 마다 정규식 매칭 | 텍스트 짧음 (< 수 KB) + compiled pattern 캐싱. 의도된 trade-off |
| **side-effect** | `llm/{gemini,anthropic}.py:generate` | 자동 주입이 도메인 의도 가림 (ctx.model=None 의도여도 어댑터 주입) | OOS-8 명시. 도메인이 sentinel 패턴 직접 구현 |

---

## 6. 다른 모듈 연계

- **시스템 프롬프트 7섹션 골격** — `RenderContext.model` 슬롯 + `_render_static` / `_render_dynamic` 양쪽 filter 적용. BOUNDARY 위 정적부 hash 가 모델별로 격리됨 (= 모델별 독립 캐시 키)
- **LLM 클라이언트 통합 (캐싱 흡수)** — `LLMClient.generate(ctx, *, cache_policy)` Protocol 시그니처 무변경. Gemini / Anthropic 어댑터가 자기 model 이름 자동 주입 (`model_copy` frozen ctx). KV 캐시는 모델별로 독립 키
- **어태치먼트 시스템** — `call_with_attachments` helper 가 `ctx.model` 그대로 전달. 도메인 어태치먼트 `build(ctx)` 안에서도 `ctx.model` 활용 가능 (모델별 다른 attachment 생성)
- **도구 베이스 (후속)** — Phase 4 도구 description 도 같은 `filter_model_blocks` 헬퍼 재사용. 모델별 description 변형 한 곳에 박음
- **관찰→교정→재관찰 (원칙 #5)** — CC 의 `@[MODEL: <model> <yyyy-mm>]` 마커 패턴. 현재는 모델 이름 glob 만, 후속 단계에서 날짜 매칭 검토

---

## 7. 데모 노트북

- 위치: `notebooks/phase-3-5-model-prompts-demo.ipynb`
- 4부 골격:
  - **Setup**: import + registry snapshot/restore (대화형 격리)
  - **1부 베이스**: filter_model_blocks 단독 호출 + 매칭/strip/None 케이스
  - **2부 register/override**: 도메인 PromptSection 안에 마커 박기 + `render(ctx)` 결과 확인
  - **3부 escape hatch + 위험 가드**: 어댑터 자동 주입 / 중첩 마커 ValueError / 정적 hash 격리 시연
  - **cleanup**: registry restore
  - **다른 모듈 연계**: mock GeminiClient + AnthropicClient — 두 어댑터 다른 model 자동 주입 + 다른 hash 시연
  - **실습 4개**: (a) 도메인 섹션 모델 분기 작성, (b) 자체 catalog 정의 + ctx 박기, (c) 도구 description 시뮬레이션, (d) 캐시 격리 검증 (3 모델 다른 hash)

---

## 8. Public API

```python
# best_agent_base/prompts/model_filter.py (신규)
def filter_model_blocks(text: str, model: str | None) -> str:
    """매칭 시 keep, 미매칭 시 strip, None 시 모든 블록 strip, 중첩 시 ValueError."""

# best_agent_base/prompts/render.py (RenderContext 슬롯 추가)
class RenderContext(BaseModel):
    ...
    model: str | None = None  # Phase 3.5

# best_agent_base/llm/gemini.py + anthropic.py (변경)
class GeminiClient:
    async def generate(self, ctx, *, cache_policy=None):
        if ctx.model is None:
            ctx = ctx.model_copy(update={"model": self._profile.model.value})
        ...

class AnthropicClient:
    async def generate(self, ctx, *, cache_policy=None):
        if ctx.model is None:
            ctx = ctx.model_copy(update={"model": self._model})
        ...
```
