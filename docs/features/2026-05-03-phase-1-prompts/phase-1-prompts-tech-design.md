# 개발방향: Phase 1 — 시스템 프롬프트 기법 (정적/동적 분리)

> **For agentic workers:** This document is the technical spec (architecture, components, data, interfaces, decisions, risks, test strategy). It is anchored to `phase-1-prompts-requirements.md` (the PRD) and consumed by `phase-1-prompts-implementation-plan.md` (step-by-step plan). NEXT STEP: invoke `writing-plans` skill (or run `/write-plan`) to produce `phase-1-prompts-implementation-plan.md` from this design. Do NOT include step-by-step implementation tasks here — those belong in the plan.

## 1. 아키텍처 개요

```
┌─────────────────────────── best_agent_base.prompts ───────────────────────────┐
│                                                                                │
│   sections.py            registry.py            render.py            boundary.py│
│   ┌─────────────┐        ┌──────────────┐       ┌─────────────────┐  ┌────────┐│
│   │ Protocol    │        │ Singleton    │       │ render(ctx)     │  │ BOUND_ ││
│   │ PromptSection│ <──── │ SectionReg.  │ ────> │ → 정적7섹션      │  │ MARKER ││
│   │             │        │  register()  │       │   + BOUNDARY    │  │        ││
│   │ 7 base      │        │  get(name)   │       │   + 동적묶음     │  │ dang.. ││
│   │ instances   │        │              │       │                 │  │ uncach ││
│   └─────────────┘        └──────────────┘       │ get_static_hash │  └────────┘│
│         ▲                       ▲                │ (sha256[:16])   │      ▲    │
│         │                       │                └─────────────────┘      │    │
│         │ override              │ register                                │    │
│         │                       │                                         │    │
│   ┌─────┴───────────────────────┴─────────────────────────────────────────┴──┐ │
│   │  Domain Project (e.g. coding agent / medical agent)                     │ │
│   │  - 자기 Section 클래스 작성 (PromptSection Protocol 만족)                 │ │
│   │  - registry.register("Intro", CodingIntro())                            │ │
│   │  - 비동기 fetch 가 필요하면 자기가 await 후 ctx 에 박아 넣음 (D1-7=δ)      │ │
│   └─────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

**원칙 매핑**:
- D-2 ("안 만들기"): 베이스는 슬롯/계약만, 콘텐츠는 도메인이 inject
- D-1 (정적/동적 분리): BOUNDARY 마커 1회 삽입, 앞=정적·뒤=동적
- D-8 (교체·확장): SectionRegistry.register() 로 베이스 0줄 수정
- D-13: `__init__.py` docstring-only 유지 (re-export 금지)

**sync 영구 (D1-7=δ)**: `PromptSection.render(ctx) → str` 는 모든 Phase 동안 sync. 비동기 fetch 는 도메인·호출자 책임.

## 2. 영향 받는 컴포넌트/파일

**신규 파일** (`best_agent_base/prompts/`):

| 파일 | 책임 | 매핑된 FR |
|---|---|---|
| `__init__.py` | docstring-only (D-13) | NFR-4 |
| `sections.py` | `PromptSection` Protocol + 7 베이스 섹션 인스턴스 (`Intro`, `System`, `DoingTasks`, `ExecutingActions`, `UsingTools`, `ToneStyle`, `OutputEfficiency`) | FR-1, FR-4, FR-5 |
| `registry.py` | `SectionRegistry` 싱글톤 + `register(name, section)` / `get(name)` API + 모듈 로딩 시 7 베이스 자동 등록 (NFR-1) | FR-3 |
| `render.py` | `render(ctx) → str`, `get_static_hash(ctx) → str`, `RenderContext(BaseModel)` | FR-2, FR-4, FR-7 |
| `boundary.py` | `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 상수, `dangerous_uncached(name, content, reason) → DangerousUncached` 헬퍼 | FR-2, FR-6 |

**신규 테스트 파일** (`tests/`): `test_prompts_sections.py`, `test_prompts_render.py`, `test_prompts_static_stability.py`, `test_prompts_registry.py`, `test_prompts_dangerous_uncached.py`, `test_prompts_cache_slot.py`, `test_no_domain_vocab.py` — §7 참조.

**수정 없음**: Phase 0 의 `Settings`, `llm/`, 9 서브패키지 `__init__.py`, `docker-compose.yml`, `pyproject.toml` (deps 추가 없음 — pydantic 기존 사용).

## 3. 데이터 모델/스키마 변경

**DB / 환경변수 / 디스크 스키마: 변경 없음** (NFR-4).

**메모리 모델 (Python 객체) — 신규**:

```python
# sections.py
class PromptSection(Protocol):
    name: str
    static: bool
    def render(self, ctx: "RenderContext") -> str: ...

# render.py
class RenderContext(BaseModel):
    """베이스는 빈 모델. 도메인/Phase 가 필드 추가."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    # 향후 Phase 2+: current_time, tools, attachments 등

# boundary.py
class DangerousUncached(BaseModel):
    """dangerous_uncached() 가 반환하는 객체. PromptSection 인터페이스 만족."""
    model_config = ConfigDict(frozen=True)
    name: str
    content: str
    reason: str = Field(min_length=1)  # 빈 문자열 거부 (R-4)
    static: bool = True               # 정적 영역에 들어가지만 의도적 cache-break
    def render(self, ctx: "RenderContext") -> str: ...
```

`SectionRegistry`: 모듈-레벨 싱글톤 인스턴스. 내부 상태 = `dict[str, PromptSection]`. NFR-1 충족.

## 4. 외부 인터페이스

**REST/GraphQL/events: 없음** (Phase 14 까지 OOS).

**Python public API** (`best_agent_base.prompts` 모듈):

```python
# 직접 import 만 허용 (best_agent_base/__init__.py 는 docstring-only — D-13)

from best_agent_base.prompts.sections   import PromptSection
from best_agent_base.prompts.registry   import registry  # 싱글톤 인스턴스
from best_agent_base.prompts.render     import render, get_static_hash, RenderContext
from best_agent_base.prompts.boundary   import (
    SYSTEM_PROMPT_DYNAMIC_BOUNDARY,
    dangerous_uncached,
    DangerousUncached,
)
```

**도메인 사용 예**:
```python
class CodingIntro:
    name = "Intro"; static = True
    def render(self, ctx): return "You are a coding agent..."

registry.register("Intro", CodingIntro())
prompt = render(RenderContext())  # str
```

## 5. 핵심 결정 + 대안 비교

| ID | 결정 | 채택안 | 대안 (기각 이유) |
|----|------|--------|------|
| **D1-1** | 파일 분할 | **4파일** (sections/registry/render/boundary) | 1파일 통합 (책임 섞임 — Phase 4·11 import 시 비대화) / 6파일 섹션별 분리 (베이스는 슬롯만 → 과잉) |
| **D1-2** | PromptSection 추상 | **`Protocol`** (구조적 타이핑) | `ABC` (도메인 상속 강제 — duck typing 친화 X, cogito 같은 외부 코드 결합도↑) |
| **D1-3** | SectionRegistry 형태 | **싱글톤 in-memory dict** | `ContextVar` (Phase 14 멀티-요청 시점에 재검토 — Phase 1 단일 프로세스, register 1회 가정으로 과잉) |
| **D1-4** | RenderContext | **빈 Pydantic `BaseModel(frozen=True)`** | `dict[str, Any]` (타입 안전 X) / `dataclass` (cogito `ModelProfile` Pydantic 일관성 깨짐) |
| **D1-5** | `dangerous_uncached` 시그니처 | **`(name: str, content: str, reason: str)` 셋 다 필수, `reason` `min_length=1`** | CC 와 동일 `compute` 콜백 (Phase 1 단순화 — lazy 가 필요해지면 Phase 2+ overload 추가) |
| **D1-6** | BOUNDARY 마커 문자열 | **`__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` (CC 와 정확히 동일)** | 다른 문자열 (CC 의 `splitSysPromptPrefix` 같은 도구 차용 못함) |
| **D1-7** | sync vs async | **(δ) sync 영구 + 도메인 fetch 책임** | (α) sync 후 미래 breaking (도메인 코드 깨짐) / (β) async-first (Phase 1 도 `asyncio.run` 강제·과잉) / (γ) Hybrid (코드량 2배·디버깅↑) |
| **D1-8** | 정적 해시 알고리즘 | **`hashlib.sha256` hex digest 첫 16자** | blake2b/md5 (stdlib 표준 우선, 충돌 risk 무시 가능, 16자 충분) |
| **D1-9** | 금칙어 목록 위치 | **`tests/test_no_domain_vocab.py` 직접 리스트** | `best_agent_base/prompts/forbidden_terms.py` 런타임 (테스트-only 가드, 프로덕션 코드 오염 X) |

## 6. 위험/사이드이펙트

| ID | 위험 | 카테고리 | 우선순위 | mitigation 방향 (구현계획서 §2 에서 구체화) |
|----|------|---------|------|---|
| **R-1** | SectionRegistry 싱글톤 — 멀티스레드/async 동시 register 시 race | race | low | Phase 1: register 1회 → read-many 가정. Phase 14 시점에 ContextVar 재검토 |
| **R-2** | `best_agent_base/__init__.py` 에 prompts re-export 추가 → D-13 위반 (Phase 0 T6 1회 발견 이력) | breaking | high | `tests/test_init_purity.py` (또는 smoke 확장) 에 docstring-only assertion 추가 |
| **R-3** | 정적 섹션 안에 동적 콘텐츠 (현재시각·랜덤 ID) 섞이면 hash turn-별 변동 → 캐시 깨짐 | perf | high | `test_prompts_static_stability.py` — N회 호출 hash 동일성 검증 (FR-4 / AC-5) |
| **R-4** | `dangerous_uncached(name, content, "")` — reason 빈 문자열 가능 | side-effect | medium | `DangerousUncached.reason: Field(min_length=1)` Pydantic 검증 + 단위 테스트 |
| **R-5** | BOUNDARY 마커가 도메인 콘텐츠 안에 우연 등장 → split 로직 파괴 | side-effect | low | `render()` 내부에서 도메인 출력에 마커 포함 여부 검사 → 발견 시 `ValueError` |
| **R-6** | 금칙어 검증 false fail (예: "code" 일반 영어) | breaking | medium | regex `\b` boundary + 도메인-특화 단어만 (`PEP`, `pytest`, `patient` 등). 일반 영어 단어 제외 |
| **R-7** | 도메인이 §4 (위험 작업 가드) override 시 약한 가드 등록 가능 | side-effect | medium | 베이스 책임 밖 → §4 베이스 섹션 docstring 에 "override 시 안전 약화 주의" 명시 |

## 7. 테스트 전략

**범위**: 단위 테스트만 (Phase 1 외부 IF 없음 → integration / contract 불필요).

| 테스트 파일 | 검증 대상 | FR / AC / R 매핑 |
|---|---|---|
| `tests/test_prompts_sections.py` | 7섹션 인스턴스 존재 + Protocol 시그니처 + name/static 속성 | FR-1 / AC-2 |
| `tests/test_prompts_render.py` | `render(ctx)` 호출 → BOUNDARY 마커 정확히 1회, 정적 앞·동적 뒤 순서, 마커 우연 포함 시 ValueError | FR-2 / AC-1 / AC-3 / AC-4 / R-5 |
| `tests/test_prompts_static_stability.py` | 동일 ctx → 정적 섹션 hash N회 동일 (정적 안정성) | FR-4 / AC-5 / R-3 |
| `tests/test_prompts_registry.py` | register/override 동작 + RenderContext 빈 BaseModel 인스턴스화 + 싱글톤 idempotency | FR-3 / AC-6 / NFR-1 |
| `tests/test_prompts_dangerous_uncached.py` | reason 누락/빈문자열 → ValidationError, 정상 호출 → 반환 객체 | FR-6 / AC-7 / R-4 |
| `tests/test_prompts_cache_slot.py` | `get_static_hash(ctx)` 외부 호출 가능 + 동일 ctx → 동일 hash | FR-7 / AC-8 |
| `tests/test_no_domain_vocab.py` | `best_agent_base/prompts/` 하위 .py grep — 금칙어 (`PEP`, `pytest`, `patient`, `HIPAA`, `portfolio` 등) `\b` boundary 검증 | NFR-3 / AC-9 / R-6 |
| `tests/test_init_purity.py` | `best_agent_base/__init__.py` + `best_agent_base/prompts/__init__.py` docstring-only assertion | NFR-4 / R-2 |

**금칙어 카테고리 후보** (test_no_domain_vocab.py 시드):
- 코딩: `PEP`, `type hint`, `pytest`, `npm`, `git`
- 의료: `patient`, `diagnosis`, `HIPAA`
- 금융: `portfolio`, `KYC`, `transaction`

**회귀**: 기존 29 tests + 신규 ≥ 20 tests → 모두 GREEN (AC-10), ruff clean (NFR-4).

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 11:55] [개발방향-수정]
- **id**: CH-20260503-002
- **이유**: 신규 기술 설계 (Phase 1 — 7섹션 + 정적/동적 분리 골격 tech-design 최초 작성)
- **무엇이**: phase-1-prompts-tech-design.md 전체 (§1 아키텍처, §2 컴포넌트 5+8파일, §3 데이터모델 3객체, §4 public API, §5 D1-1..D1-9, §6 R-1..R-7, §7 테스트 8파일)
- **영향범위**: 없음 (최초 생성)
- **연관 항목**: CH-20260503-001 (PRD)
