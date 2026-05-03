# 인수인계 문서 — best_agent_base

> **다음 세션이 이 한 파일만 읽어도 즉시 이어갈 수 있게 작성.**
> 마지막 갱신: 2026-05-03 (Phase 0 완료 + LLM 모델 카탈로그 보강 후)

---

## 🎯 Goal — 프로젝트 최종 목적

**Claude Code(TS·프론트엔드 CLI)의 하네스 기법을 파이썬 백엔드(FastAPI + SQLAlchemy)로 포팅한, 모든 에이전트 프로젝트의 Base 모듈을 만든다.**

- 도메인 무관 — 어떤 에이전트 프로젝트든 `import best_agent_base` 한 번으로 시작.
- **인터페이스·계약 중심 골격** (추상 클래스 / Protocol / Pydantic 스키마 / 엔드포인트 시그니처).
- 다른 프로젝트는 **상속·구현·교체**만 하면 됨 (원칙 #8).
- 14 Phase 로드맵의 마지막은 FastAPI 엔드포인트로 에이전트 노출.
- 사용자 실력 향상도 목적 → **스텝바이스텝**, 한꺼번에 다 짜지 않음.

자세한 마스터 로드맵: [`TODO.md`](./TODO.md)

---

## 📍 Current Progress

### Phase 0 — 프로젝트 골격 ✅ 완료 (tag `phase-0-skeleton-done`)

**산출물 (commit b5f9870 ~ 94f3b2d)**:
- 9 서브패키지 디렉토리 + `__init__.py` (docstring-only, D-13)
- `best_agent_base/config.py` — `Settings(BaseSettings)` 6 필드, lazy 인스턴스화 (D-12)
- `pyproject.toml` — 11 런타임 deps + 4 dev deps + `[tool.ruff]` + `[tool.pytest.ini_options]`
- `docker-compose.yml` — postgres host **5435** + redis 6379 + healthchecks
- `.env.example`, README Setup 4 단계, `docs/local-dev-setup.md`
- `tests/` — smoke 11 + settings 6 = **17 tests pass**, ruff clean
- `scripts/change_id.py` — js-super:change-history 헬퍼

**Phase 0 후속 보강 (commit 1e5914a, 94f3b2d)** — cogito 패턴 차용:
- `best_agent_base/llm/models.py` — `class GeminiModel(StrEnum)` (FLASH_LITE/FLASH/PRO)
- `best_agent_base/llm/profiles.py` — `ModelProfile(BaseModel, frozen)` + 프리셋 (DEFAULT_CHAT, DEFAULT_REASONING)
- `best_agent_base/llm/gemini.py` — `get_gemini(profile=DEFAULT_CHAT)` (raw string/숫자 인자 금지)
- `tests/test_llm_profiles.py` — **12 cases** (enum/디폴트/검증/frozen/프리셋/raw string 거부)
- 현재 **29 tests pass** (smoke 11 + settings 6 + llm_profiles 12)

**문서 산출물 (전부 main 에 commit)**:
- [`TODO.md`](./TODO.md) — 14 Phase + 8 설계 원칙 + 참조 베이스 트리
- `docs/features/2026-05-03-phase-0-skeleton/` — PRD + tech-design + impl-plan (CH-001..CH-006)
- `docs/local-dev-setup.md` — Docker 사용 가이드

### git 상태
- 브랜치: `main` (HEAD `94f3b2d`)
- `phase-0-skeleton-impl` 브랜치/워크트리 — 머지 후 정리됨
- **사용자의 `.worktrees/병렬구현-테스트` 워크트리는 절대 건드리지 말 것** (사용자 연구용)
- origin (GitHub `LonerStayle/best_agent_base`) — push 안 함 (origin/main 은 `4785927` 초기 부트스트랩)
- tag `phase-0-skeleton-done` → `68c91a9`

---

## ✅ What Worked

- **`js-super` 풀 사이클 (brainstorm → design → write-plan → execute-plan → finishing-branch)** — Phase 0 한 바퀴 깨끗이 완성. 매 단계의 게이트(verify-spec, change-history, 단일 승인)가 정합성 보장.
- **Subagent-driven-development** — 12 implementer + 11 reviewer + 1 final = 24회 dispatch. 메인 컨텍스트 절약 + 매 task 독립 검증.
- **TDD RED → GREEN 사이클**: smoke 테스트 RED 먼저(commit `329ef8a`), 9 서브패키지 생성으로 GREEN(`a51931c`). settings 도 동일 패턴.
- **D-12 (lazy 인스턴스화) + D-13 (`__init__.py` 빈 상태)** — 둘 다 자동 테스트로 강제 (test_no_module_level_instance, grep 점검).
- **2-Tier 저장 모델 (Postgres 영속 + EphemeralCache/BlobStore Protocol 슬롯)** — 백엔드 환경 (재시작·다중 인스턴스) 에서 깨지지 않는 설계.
- **Worktree-per-Phase 패턴** — `.worktrees/<phase-name>-impl` 에서 작업 → main 머지 → 워크트리 정리. main 깨끗.
- **change-history cross-link 패턴** — PRD 변경(CH-002) ↔ tech-design(CH-003) ↔ plan(CH-004) ↔ 코드(CH-005, CH-006) 연결.

---

## ❌ What Didn't Work / 주의

- **첫 시도에 push to origin 시도 → 권한 거절** — option 1 (로컬 머지) 선택 시 push 별도 승인 필요. push 가 필요하면 사용자에게 명시 요청.
- **CC `src/contextCollapse/` 와 `src/services/compact/snipCompact.js` 는 TS 본체 비공개** (`.js` 만 require). Phase 9 구현 시 `system_info/query-context-management.md` 의 발동 조건/Before-After 만으로 알고리즘 직접 설계 필요. (TODO.md Phase 9 의 ⚠️ 참고)
- **D-13 위반은 후속 발견 가능** — Phase 0 의 T6 코드리뷰가 기존 `best_agent_base/__init__.py` 의 편의 import (`get_gemini` re-export) 위반 발견. T6.5 fix(`b1a8e86`)로 정렬. 후속 Phase 도 신규 추상 추가 시 `__init__.py` docstring-only 룰 재확인.
- **`extra="ignore"` 문제** — pydantic-settings 가 typo 된 env 키를 silently ignore. 코드 리뷰 권고로 Phase 11 Hooks 시점에 `extra="forbid"` 전환 검토 (Phase 1+ 그루밍 노트).
- **pytest 9.x 자동 해석** — 사용자 plan 은 8.x 라 적었지만 uv 가 9.0.3 자동 선택. asyncio_mode="auto" 호환 확인됨.
- **사용자 글로벌 CLAUDE.md 룰**: "탐색/플래닝 → 서브에이전트, 실행 → 메인" — 이번엔 사용자가 명시적으로 subagent-driven 선택해서 실행도 서브로 함. 다음 Phase 부터는 사용자 기본 룰 (실행=메인) 우선 고려, 명시 변경 시에만 서브.

---

## 🔧 핵심 설계 원칙 (8가지, 모든 Phase 관통)

> [`TODO.md` §🧭 설계 원칙](./TODO.md#-설계-원칙-모든-phase에-관통) 참조

1. 정적/동적 분리 (Caching Boundary)
2. "안 만들기" 원칙 (분류기·라우터·상태머신 만들지 마)
3. 조용한 정규화 (Silent Normalization)
4. 3그룹/3레이어 병렬 분담
5. 관찰→교정→재관찰 (`@[MODEL: ...]` 마커)
6. 에러는 모델 피드백 (envelope 반환)
7. 격리된 컨텍스트 (Subagent Isolation)
8. **교체·확장 가능성 (Swappable & Extensible)** — `register()` 패턴, 베이스 0줄 수정으로 도메인 확장

---

## 📚 참조 베이스 (Source of Truth)

- 루트: `/Users/goldenplanet/jinsup_space/CC/`
- 분석 .md 들 + `system_info/` + `tools_info/` + `cc-analysis/` + `src/`
- **구현(`/execute-plan`) 진입 시 룰**: 관련 분석 .md 다시 읽기 → `CC/src/` grep·glob → 시그니처/검증 패턴 참고해 파이썬으로 옮김. **md 와 src 둘 다 본다** (md=의도, src=디테일).
- 자세한 트리: [`TODO.md` §📚 참조 베이스](./TODO.md#-참조-베이스-source-of-truth)

---

## 🛤️ Next Steps — Phase 1 시작

> **다음 세션이 사용자에게 "Phase 1 가자" 신호 받으면 아래 흐름으로:**

### Phase 1 — 시스템 프롬프트 기법 (정적/동적 분리)

> [`TODO.md` §🧱 Phase 1](./TODO.md#-phase-1--시스템-프롬프트-기법-정적동적-분리) 참조

**핵심**: 7 섹션 골격을 **도메인-중립 슬롯**으로 (콘텐츠는 도메인이 register/주입). 코딩 어휘 베이스에 박지 않음.

**참조 (필수)**:
- `prompt-engineering-techniques.md` — 정적/동적 경계 마커 메커니즘
- `에이전트-성능-결정요인-총정리.md` — 14 프롬프트 기법
- **`시스템프롬프트-7섹션-요약.md`** — 7 섹션 각각의 주제·핵심 (1차 자료) — 다음 세션이 brainstorming 단계에서 먼저 읽기.

**시작 시퀀스**:
1. **새 worktree 생성** — `git worktree add -b phase-1-prompts-impl .worktrees/phase-1-prompts-impl` (또는 `/worktree phase-1-prompts-impl`)
2. cd 워크트리 → `js-super:brainstorming` 호출, slug=`phase-1-prompts`
3. 사용자 사전 답변(이미 TODO.md 에 들어가 있음) 활용:
   - 7 섹션 골격을 Python 데이터 구조 (Section Protocol + Domain override hook)
   - `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 마커
   - `dangerous_uncached(name, content, reason)` 헬퍼
   - 정적 섹션 해시 → 캐시 적중률 측정 (Phase 2 캐시 메트릭과 연동)
   - 단위 테스트: 정적 안정성 / 동적 변동 / 도메인 콘텐츠 교체
4. brainstorming → designing-direction → writing-plans → subagent-driven 실행

**Phase 1+ 그루밍 노트** (Phase 0 final code review 도출 — 적절한 Phase 에 반영):
1. ~~README Status 라벨 갱신~~ ✅ 완료
2. `main.py` 의 `load_dotenv()` 직접 호출 → `Settings()` 진입점 사용 (Phase 1 또는 Phase 11 Settings 시스템 시점)
3. `tests/conftest.py` 도입 (공통 async fixture 필요 시)
4. `Settings.log_level` 을 `Literal[DEBUG, INFO, WARNING, ERROR, CRITICAL]` (Phase 11 Hooks 시점)
5. `Settings.agent_state_dir` 을 `Path` 로 정규화 (Phase 9)
6. `extra="ignore"` → `extra="forbid"` 검토 (Phase 11)

---

## 🛠 환경 / 명령 빠른 참조

```bash
# 작업 디렉토리
cd /Users/goldenplanet/jinsup_space/best_agent_base

# 환경 검증
uv sync                         # deps 설치
uv run pytest -v                # 29 tests
uv run ruff check .             # All checks passed!
docker compose up -d            # postgres(5435) + redis(6379)

# js-super 워크플로우
/worktree phase-1-prompts-impl  # 새 워크트리
/brainstorm                     # PRD
/design                         # 기술 설계
/write-plan                     # 구현 계획
/execute-plan                   # 실행 (또는 subagent-driven-development)

# 변경이력
uv run python -m scripts.change_id docs/features/<date>-<slug>
```

---

## 🔑 Quick Facts

- **Python**: 3.12+ 강제 (`.python-version`, `pyproject.toml requires-python`)
- **Default Gemini model**: `GeminiModel.FLASH` (`gemini-3-flash`) via `DEFAULT_CHAT` 프로파일
- **Postgres host port**: **5435** (사용자 환경에 5432 다른 프로젝트 점유)
- **Redis port**: 6379 (Optional, EphemeralCache backend swap)
- **Workflow plugin**: `js-super` 만 사용 (superpowers 등 안 씀)
- **사용자 이메일**: axtech@goldenplanet.co.kr
- **GitHub repo**: `LonerStayle/best_agent_base` (origin 설정됨, push 안 함)

---

## 📋 다음 세션 시작 체크리스트

새 세션 시작 시:

1. [ ] 이 `HANDOFF.md` 한 번 통독
2. [ ] `git status && git log --oneline -10` 으로 현재 상태 확인
3. [ ] `uv run pytest && uv run ruff check .` 가 GREEN 인지 확인
4. [ ] 사용자가 "Phase 1 가자" 또는 다른 요청 — 그에 맞춰 진입
5. [ ] Phase 진입이면: 위 "시작 시퀀스" 그대로 따라가기
6. [ ] 새 worktree 만들 때 `.worktrees/병렬구현-테스트` 는 절대 건드리지 말 것 (사용자 연구용)
