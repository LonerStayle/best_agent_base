# 요구사항: Phase 1 — 시스템 프롬프트 기법 (정적/동적 분리)

> **For agentic workers:** This document is the PRD (planning-level only). NEXT STEP: invoke `designing-direction` skill (or run `/design`) to produce `phase-1-prompts-tech-design.md` from this document. Do NOT add tech decisions or implementation details here — those belong in the next two artifacts.

## 1. 배경/목적

Claude Code 가 7개 정적 섹션 + 동적 부 + `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커로 시스템 프롬프트를 구성해 KV 캐시 적중률을 극대화하는 패턴을, **도메인-중립 골격으로** `best_agent_base.prompts` 에 옮긴다. 베이스는 7섹션의 **이름·순서·정적 플래그·렌더 시그니처**만 정의하고, 실제 콘텐츠는 도메인 프로젝트가 register/override 로 주입한다. Phase 2 의 캐시 메트릭과 연동될 **정적 섹션 해시 슬롯**까지 만든다 (실제 KV 캐시 측정은 Phase 2).

**Why now**: Phase 0 의 `Settings` + 9 서브패키지 골격 위에 처음으로 의미있는 추상이 들어가는 단계. 이후 Phase (도구·HITL·context) 가 이 7섹션 슬롯에 콘텐츠를 꽂는 식으로 확장되므로 **여기서 슬롯 구조가 잘못되면 14 Phase 전체에 파급**.

## 2. 사용자 스토리 / 시나리오

> 본 PRD 의 "사용자" = `best_agent_base` 의 직접 소비자 (도메인 에이전트를 만드는 사람). 도메인 에이전트의 최종 사용자(end-user) 는 도메인 프로젝트의 PRD 에서 다룬다.

- **US-1 (도메인 콘텐츠 주입)**: 도메인 에이전트를 만들 때 7섹션 골격을 그대로 받고, **§1·§3 같은 콘텐츠가 필요한 자리에만 도메인 텍스트를 register** 하면 끝나야 한다. 베이스 코드 수정 없이.
- **US-2 (부분 override)**: 도메인이 §4 (위험 작업 가드) 같은 일부 섹션을 자기 규칙으로 **덮어써야 할 때**, 그 섹션만 갈아끼우고 나머지 6개는 베이스 기본값 그대로 동작해야 한다.
- **US-3 (정적/동적 검증)**: 베이스 작업 중 **정적 섹션이 매 turn 같은 출력을 내는지 자동으로 잡아낼 수 있어야** 한다 (해시 안정성 테스트). 캐시 깨지는 상황을 코드 단계에서 발견.

## 3. 기능 요구사항 (FR)

- **FR-1 (7섹션 골격)**: 베이스는 §1 Intro / §2 System / §3 Doing tasks / §4 Executing actions / §5 Using your tools / §6 Tone & style / §7 Output efficiency 의 7개 섹션을 **이름·순서·정적 플래그·렌더 시그니처** 로 정의한다. 각 섹션은 도메인-중립 기본값을 갖는다.
- **FR-2 (정적/동적 경계 마커)**: 베이스는 정적 섹션 묶음과 동적 섹션 묶음 사이에 정확한 문자열 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커를 1회 삽입한다.
- **FR-3 (섹션 register/override)**: 도메인은 베이스 코드 수정 없이 (a) 섹션 콘텐츠를 주입하거나 (b) 특정 섹션 인스턴스 자체를 갈아끼울 수 있다. 등록되지 않은 섹션은 베이스 기본값을 사용한다.
- **FR-4 (정적 섹션 안정성)**: 동일한 입력 컨텍스트에 대해 정적 섹션의 렌더 결과는 매번 동일한 문자열·동일한 해시를 반환한다.
- **FR-5 (동적 섹션 변동 허용)**: 동적 섹션은 매 호출마다 컨텍스트에 따라 다른 결과를 반환할 수 있어야 한다 (예: 현재 시각, 도구 카탈로그, 첨부 파일 목록).
- **FR-6 (`dangerous_uncached` 헬퍼)**: 정적 영역에 캐시 비친화적 콘텐츠를 의도적으로 넣어야 할 때, `dangerous_uncached(name, content, reason)` 형태의 명시 헬퍼를 통해서만 가능하다. `reason` 인자는 필수 — 기술 부채 추적 목적.
- **FR-7 (캐시 측정 슬롯)**: 베이스는 정적 섹션 묶음의 해시를 외부에서 조회 가능한 함수로 노출한다. 실제 KV 캐시 적중률 측정 (Phase 2) 은 이 슬롯 위에 얹는다.

## 4. 비기능 요구사항 (NFR)

- **NFR-1 (싱글톤 registry)**: 섹션 인스턴스는 모듈 로딩 시 1회만 인스턴스화. turn 마다 새로 만들지 않는다.
- **NFR-2 (테스트 3축)**: `best_agent_base/prompts/` 하위 public 심볼은 단위 테스트 보유. 정적 안정성 / 동적 변동 / 도메인 override 3축 모두 검증.
- **NFR-3 (도메인 의존성 0)**: 베이스 prompts 모듈은 도메인 어휘 (코딩/의료/금융 등) 를 일체 포함하지 않는다. **금칙어 목록을 테스트로 박아 자동 검증** (예: "PEP", "type hint", "patient", "diagnosis", "portfolio" 등 발견 시 실패).
- **NFR-4 (기존 골격 준수)**: D-13 (`__init__.py` docstring-only) 위반 금지. Phase 0 의 `Settings` 변경 없음. ruff clean + 기존 29 tests + 신규 테스트 모두 GREEN.
- **NFR-5 (관찰 가능성 슬롯)**: `dangerous_uncached` 사용 시 `reason` 이 로그 가능한 형태로 보존. 실제 로깅은 Phase 11 Hooks 에서 연결.

## 5. 범위 밖 (Out of Scope)

- 실제 KV 캐시 적중률 측정·로깅 (Phase 2 종속, FR-7 은 슬롯까지만)
- 도구 카탈로그 실제 구현·등록 메커니즘 (Phase 4 종속)
- HITL · 도메인 콘텐츠 텍스트 본체 (도메인 프로젝트 책임)
- 실제 로깅 인프라 연결 (Phase 11 Hooks 종속, NFR-5 는 보존만)
- 렌더 성능 ms 단위 측정 (Phase 1 범위 아님 — 프롬프트 조합은 LLM 호출 시간 대비 무시 가능)
- end-user (도메인 에이전트의 최종 사용자) 시나리오 (US 는 베이스 직접 소비자만)
- Phase 0 `Settings` 변경 / 새 환경변수 추가 (NFR-4 로 명시)
- Phase 11 의 `extra="forbid"` 전환 등 Settings 그루밍 (Phase 11 시점)

## 6. 수용 기준 (Acceptance Criteria)

- **AC-1**: `from best_agent_base.prompts import sections, registry, render` 가 import 에러 없이 동작한다.
- **AC-2**: `sections` 모듈에 7개 섹션 인스턴스 (Intro / System / DoingTasks / ExecutingActions / UsingTools / ToneStyle / OutputEfficiency) 가 정의되어 있고, 각각 `name`, `static: bool`, `render(ctx) → str` 인터페이스를 갖는다.
- **AC-3**: `render(ctx)` 호출 결과 문자열에 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 가 정확히 1회 포함된다.
- **AC-4**: 마커 앞에 정적 섹션, 뒤에 동적 섹션이 위치한다 (순서 검증 테스트 GREEN).
- **AC-5**: 동일한 `ctx` 입력에 대해 정적 섹션의 해시는 N회 호출에서 모두 동일하다 (정적 안정성 테스트 GREEN).
- **AC-6**: 도메인이 `registry.register("Intro", custom_section)` 호출 시 베이스 코드 수정 없이 해당 섹션이 교체되고, 나머지 6개는 베이스 기본값으로 동작한다.
- **AC-7**: `dangerous_uncached(name, content, reason)` 호출 시 `reason` 이 빠지면 `TypeError`/`ValidationError` 로 거부된다.
- **AC-8**: 정적 섹션 묶음의 해시를 외부 함수 (`get_static_hash()` 또는 동등 시그니처) 로 조회 가능하다.
- **AC-9**: 베이스 prompts 모듈 grep 시 도메인 어휘 금칙어가 발견되지 않는다 — 자동 테스트로 강제.
- **AC-10 (회귀)**: 기존 29 tests + 신규 prompts 테스트 + ruff 모두 GREEN.

---
## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 11:30] [요구사항-수정]
- **id**: CH-20260503-001
- **이유**: 신규 피처 brainstorming 결과 (Phase 1 — 시스템 프롬프트 7섹션 골격 + 정적/동적 분리 PRD 최초 작성)
- **무엇이**: phase-1-prompts-requirements.md 전체 (FR-1..FR-7, NFR-1..NFR-5, OOS 8개, AC-1..AC-10, US-1..US-3)
- **영향범위**: 없음 (최초 생성)
