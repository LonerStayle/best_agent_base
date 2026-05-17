# 개발방향: Phase 3.5 — 모델별 프롬프트 변형 슬롯 (mini-phase)

> **For agentic workers:** This document is the technical spec. Anchored to `phase-3-5-model-prompts-requirements.md` (PRD CH-20260517-001), consumed by `phase-3-5-model-prompts-implementation-plan.md`. NEXT STEP: invoke `writing-plans` skill (or run `/write-plan`).

## 1. 아키텍처 개요

### 다이어그램

```
도메인 코드:
  ctx = RenderContext(model="claude-sonnet-4-5-...", ...)  ← 명시
       또는 RenderContext(...)  ← model 없음
            │
            ▼
  await client.generate(ctx, cache_policy=...)
            │
            ▼
   GeminiClient / AnthropicClient .generate()
            │
            ├─ if ctx.model is None:
            │     ctx = ctx.model_copy(update={"model": self._self_model_name()})
            │     # Gemini: self._profile.model.value / Anthropic: self._model
            │
            ▼
   split_at_boundary(ctx)  ← Phase 2
            │
            ▼
   render(ctx)  ← Phase 1
            │
   _render_static(ctx) + _render_dynamic(ctx)
            │
            ▼
   filter_model_blocks(text, ctx.model)  ← Phase 3.5 신규 — 양쪽 적용
            │
   ┌────────┼────────┐
   │        │        │
   ▼        ▼        ▼
match keep / mismatch strip / None ⇒ all strip
            │
            ▼
   "<filtered static> ── BOUNDARY ── <filtered dynamic>"
            │
            ▼
   get_static_hash(ctx) = sha256(filtered static)[:16]
   → 같은 ctx.model 동일 hash, 다른 ctx.model 다른 hash (모델별 독립 캐시)
```

### 프로즈

베이스는 단일 helper 함수 (`filter_model_blocks`) + `RenderContext.model` 슬롯 + Phase 1 `_render_static` / `_render_dynamic` 통합 + Phase 2 어댑터 자동 model 주입 — 4개 변경점. 별도 클래스 / Protocol 추가 없음 (CC 원본 `getAntModelOverrideSection` 도 단일 함수 패턴).

`@[MODEL: <pattern>] ... @[/MODEL]` 마커는 정규식 단일 패턴으로 파싱 (`re.DOTALL` + non-greedy). `fnmatch.fnmatch(model, pattern)` 으로 glob 매칭. `model=None` 시 모든 블록 strip (조용한 정규화 — Phase 1~3 backward compat 보장).

어댑터 자동 주입은 `ctx.model_copy(update={"model": self_model_name})` 으로 frozen ctx 새로 생성. 도메인 명시 `ctx.model` 우선.

## 2. 영향 받는 컴포넌트/파일

### 신규 (1 src + 4 test)

```
best_agent_base/prompts/
└── model_filter.py                              # 신규: filter_model_blocks 헬퍼

tests/
├── test_prompts_model_filter.py                 # 신규: 단위 (FR-2, FR-3, FR-6)
├── test_prompts_model_aware_render.py           # 신규: render(ctx) 통합 (FR-4)
├── test_llm_adapter_model_injection.py          # 신규: GeminiClient / AnthropicClient 자동 주입 (FR-5)
└── test_no_domain_vocab.py                      # 확장: model_filter.py 까지 grep 범위 (NFR-1)
```

### 변경 (3 src + 1 test 확장)

```
best_agent_base/prompts/render.py                # 변경: RenderContext.model 슬롯 + _render_static/_dynamic 에 filter 적용
best_agent_base/llm/gemini.py                    # 변경: generate() 시작 ctx.model is None → self._profile.model.value 자동 주입
best_agent_base/llm/anthropic.py                 # 변경: 동일 패턴, self._model 자동 주입
tests/test_no_domain_vocab.py                    # 확장: grep dir 에 model_filter.py 포함, 어댑터는 자기 model 이름 박혀있어도 OK (예외 처리)
```

### FR → 파일 매핑

| FR | 파일 |
|---|---|
| FR-1 (RenderContext.model 슬롯) | `prompts/render.py` |
| FR-2 (@[MODEL:] 마커 시스템) | `prompts/model_filter.py` |
| FR-3 (filter_model_blocks 헬퍼) | `prompts/model_filter.py` |
| FR-4 (render(ctx) 통합) | `prompts/render.py` (_render_static / _render_dynamic) |
| FR-5 (어댑터 자동 주입) | `llm/gemini.py` + `llm/anthropic.py` |
| FR-6 (중첩 마커 거부) | `prompts/model_filter.py` (parse 중 detect → ValueError) |

## 3. 데이터 모델/스키마 변경

**N/A — DB 변경 없음.**

런타임 데이터 모델 변경 1건:
- `RenderContext.model: str | None = None` 슬롯 추가 (Pydantic frozen, 디폴트 None)

## 4. 외부 인터페이스 (API, events)

**N/A — REST / GraphQL / 이벤트 없음.**

내부 모듈 Public API 변경:

```python
# best_agent_base/prompts/model_filter.py (신규)
def filter_model_blocks(text: str, model: str | None) -> str:
    """@[MODEL: pattern] ... @[/MODEL] 블록 fnmatch 매칭 시 keep, 미매칭 시 strip.
    model=None 시 모든 마커 블록 strip (조용한 정규화).
    중첩 마커는 ValueError.
    """

# best_agent_base/prompts/render.py (RenderContext 슬롯 추가)
class RenderContext(BaseModel):
    ...
    model: str | None = None  # 신규
```

## 5. 핵심 결정 + 대안 비교 (7 결정)

### D1 — 마커 파싱: 정규식 단일 패턴 (채택)

**대안:** 토큰 파서 (lexer + 상태 머신)
**채택 이유:** 단일 레벨 마커 (중첩 거부) 라 정규식 충분. `re.findall(r"@\[MODEL:\s*([^\]]+)\]\s*(.*?)\s*@\[/MODEL\]", text, re.DOTALL)` 한 줄. 파서는 over-engineering. 중첩 detect 도 정규식 + 카운트 가능.

### D2 — model=None 시 동작: 모든 마커 블록 strip (채택)

**대안:** keep (마커 라인만 strip, 내용 보존) / ValueError (명시적 실패)
**채택 이유:** Phase 1~3 backward compat 최강 — 기존 코드 (마커 없음) 는 ctx.model 안 채워도 그대로 동작. 도메인이 새 마커 박았는데 model 안 채우면 마커 자동 무시 (조용한 정규화, 원칙 #3). ValueError 는 도메인 마찰 ↑.

### D3 — 어댑터 자동 주입: model_copy 새 ctx (채택)

**대안:** ctx 직접 mutation (`ctx.model = ...`) / generate 시그니처에 model 추가 (`generate(ctx, *, model="...")`)
**채택 이유:** ctx frozen 모델 → mutation 불가. `model_copy(update={"model": ...})` 가 Pydantic 표준 패턴. 시그니처 추가는 Phase 2 LLMClient Protocol 깸 — 무변경 유지 (B-thin).

### D4 — hash 계산 시점: filter_model_blocks 적용 후 (채택)

**대안:** filter 이전 raw 텍스트 hash (모델 무관) / 모델 이름 자체를 hash 에 포함
**채택 이유:** 같은 모델 호출 시 동일 hash (Phase 2 캐시 적중 보장), 다른 모델 호출 시 다른 hash (모델별 독립 캐시) → 정확한 캐시 격리. raw hash 는 캐시 키 충돌 (모델 다른데 같은 키), 모델 이름 hash 포함은 hash 가 모델 이름 변경에 fragile.

### D5 — 중첩 마커: ValueError (채택)

**대안:** 허용 (재귀 파싱) / 외부 마커 우선 / 내부 마커 우선
**채택 이유:** 구조적으로 모호 (`@[MODEL: a]@[MODEL: b]X@[/MODEL]@[/MODEL]` — a 매칭이면 b 의미? 둘 다? 외부 우선? 내부 우선?). 명시적 에러 + 도메인이 single-level 로 쓰게 강제 → 디버깅 쉬움. CC 의 `getAntModelOverrideSection` 도 single-level.

### D6 — fnmatch glob (채택)

**대안:** 정규식 패턴 (`re.match`) / 정확 매칭 (`==`)
**채택 이유:** fnmatch 는 stdlib + 직관적 (`claude-*`, `gemini-*`). 정규식은 도메인이 glob 잘못 쓰면 ReDoS 위험. 정확 매칭은 모델 버전 늘어날 때마다 도메인이 모든 버전 박아야 (예: `claude-sonnet-4-5-20250929` / `claude-sonnet-4-5-20251101` / ...) — 비대.

### D7 — 어댑터 model 이름 source: `self._profile.model.value` (Gemini) / `self._model` (Anthropic) (채택)

**대안:** 환경 변수 / 별도 setting / 어댑터 생성자 인자
**채택 이유:** 어댑터가 이미 자기 모델 이름 알고 있음 (Phase 0/2). 그대로 활용 = 추가 인자 / setting 없음. 도메인이 명시적으로 ctx.model 박으면 우선 사용 (override 가능).

### Gemini CLI 비교 노트 (CLAUDE.md §2 룰)

- **Claude 우위 → 베이스 흡수**: `@[MODEL: ...]` 마커는 CC `getAntModelOverrideSection` 의 정확한 백엔드 포팅. Gemini CLI 에는 동급 모델 버전별 교정 슬롯 부재.
- **Claude 우위 → 베이스 흡수**: 캐시 격리 (모델별 다른 hash) — Phase 2 의 명시적 캐시 boundary + 모델별 필터 후 hash 로, "암묵적 캐싱 의존 시 모델 변경 캐시 미스 폭발" 함정 회피.
- **Gemini wire 한계 존중**: 두 어댑터 자동 주입 시 자기 model 이름만 박음. Gemini 의 wire 한계 (text→tool→STOP) 와 무관 — 모델별 prompt 변형이 wire 한계 우회에 사용될 수 있는 슬롯.

## 6. 위험/사이드이펙트 (preliminary, 5 리스크)

### R-1 (side-effect) — `prompts/model_filter.py`

**설명:** 정규식 greedy 매칭으로 마커 잘못 닫음 — `@[MODEL: a]X@[/MODEL]Y@[MODEL: b]Z@[/MODEL]` 에서 `(.*?)` 안 쓰면 `X@[/MODEL]Y@[MODEL: b]Z` 가 a 블록 내용으로 잡힘.

**Mitigation:** `(.*?)` non-greedy + `re.DOTALL` 사용. 단위 테스트 — 2 연속 블록 케이스 명시.

### R-2 (side-effect) — `prompts/render.py:get_static_hash`

**설명:** 정적 hash 가 filter_model_blocks 결과를 입력으로 받음 → ctx.model 값이 hash 에 영향. 도메인이 같은 ctx 인스턴스를 재사용 안 하고 매번 새로 만들 때 model 박는 걸 잊으면 None 으로 fallback → 모든 마커 strip 된 hash 와 명시 모델 hash 가 다름 → 캐시 미스.

**Mitigation:** 어댑터 자동 주입 (FR-5) 으로 None 케이스 최소화. 도메인 가이드 (인터페이스 가이드) 에 "ctx.model 명시 권장" 명시. 회귀 테스트 — 같은 ctx 반복 호출 시 동일 hash 보장.

### R-3 (breaking) — `prompts/render.py:RenderContext`

**설명:** RenderContext 슬롯 추가 — Phase 1~3 가 만든 RenderContext() 호출 (11+ 사이트) 깨짐?

**Mitigation:** `model: str | None = None` 디폴트 값 → 인자 무없이 호출 가능 (Phase 1~3 backward compat). 회귀 테스트 — Phase 1 70 + Phase 2 41 + Phase 3 76 = 187 전부 GREEN 검증.

### R-4 (perf) — `prompts/model_filter.py`

**설명:** 정규식 매칭이 매 render 호출마다 실행 — 정적 7섹션 + 동적부 양쪽. 마커 없으면 regex 가 빠르게 0 match 반환하지만 오버헤드는 있음.

**Mitigation:** 텍스트 길이 짧음 (시스템 프롬프트 < 수 KB). 정규식 매칭 < 1ms. 마커 안 박힌 케이스에서 추가 비용 0 가까움 (compiled pattern 캐싱). NFR 에 명시 안 함 (의도된 trade-off, 도메인 관찰).

### R-5 (side-effect) — `llm/gemini.py` + `llm/anthropic.py`

**설명:** 어댑터 자동 주입이 도메인 의도 가림 — 도메인이 일부러 ctx.model=None 으로 "마커 다 strip 하고 싶다" 의도였는데 어댑터가 자동 채워서 마커 활성화.

**Mitigation:** 도메인이 "자동 주입 꺼" 원하면 sentinel 값 (예: `"_none_"`) 박고 filter_model_blocks 가 그걸 None 으로 취급 — OOS 8 명시 (필요시 도메인 책임). 인터페이스 가이드에 "ctx.model=None 은 어댑터가 자기 model 로 자동 채움" 명시.

## 7. 테스트 전략

### 7-1. 단위 (3 신규)

| 파일 | 커버 | 비고 |
|---|---|---|
| `test_prompts_model_filter.py` | FR-2, FR-3, FR-6, R-1 | filter_model_blocks: 매칭/strip/None/중첩 거부/2 연속 블록/glob 패턴 (claude-*, gemini-*, *, claude-sonnet-4-*) |
| `test_prompts_model_aware_render.py` | FR-4, R-2 | render(ctx) 모델별 다른 hash, 같은 모델 동일 hash, 정적/동적 양쪽 filter 적용 |
| `test_llm_adapter_model_injection.py` | FR-5 | mock SDK — Gemini ctx.model=None → self._profile.model.value 자동 주입, Anthropic ctx.model=None → self._model. ctx.model 명시 시 우회 |

### 7-2. invariant (1 확장)

| 파일 | 커버 |
|---|---|
| `test_no_domain_vocab.py` (확장) | NFR-1 — grep 범위에 `model_filter.py` 추가. 단 어댑터 안 자기 model 이름 (Gemini `_profile.model.value` / Anthropic `_model`) 은 예외 — 이미 Phase 0/2 코드에 박혀있음 |

### 7-3. 회귀 invariant (Phase 1~3)

전체 테스트 GREEN — Phase 1 70 + Phase 2 41 + Phase 3 76 = 187 회귀 0건. R-3 mitigation 핵심 검증.

### 7-4. 테스트 카운트 추정

- 현재 187
- Phase 3.5 신규: filter (~10) + render (~5) + adapter (~6) + grep 확장 (~3) = ~24
- **예상: ~211 GREEN**

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-17 12:30] [개발방향-수정]
- **id**: CH-20260517-002
- **이유**: A+D 조합 tech-design (RenderContext.model 슬롯 + filter_model_blocks 헬퍼 + render 통합 + 어댑터 자동 주입 + 5 리스크)
- **무엇이**: phase-3-5-model-prompts-tech-design.md 전체 (§1 아키텍처 + §2 영향 파일 + §3 N/A + §4 N/A + §5 7결정 + §6 5리스크 + §7 테스트 전략)
- **영향범위**: 없음 (최초 생성). PRD CH-20260517-001 의 FR-1..6 + NFR-1..4 + AC-1..12 모두 trace (verify PASS, 메인 직접). 사용자 자동 진행 모드로 docs-pretty / 별도 승인 게이트 스킵
- **연관 항목**: CH-20260517-001 (PRD)
