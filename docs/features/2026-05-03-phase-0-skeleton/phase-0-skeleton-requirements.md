# 요구사항: Phase 0 — 프로젝트 골격 (phase-0-skeleton)

> **For agentic workers:** This document is the PRD (planning-level only). NEXT STEP: invoke `designing-direction` skill (or run `/design`) to produce `phase-0-skeleton-tech-design.md` from this document. Do NOT add tech decisions or implementation details here — those belong in the next two artifacts.

## 1. 배경 / 목적

**배경**
- `best_agent_base` 는 14개 Phase 에 걸쳐 인터페이스·계약을 뚫는 베이스 모듈을 만든다. (전체 로드맵: `TODO.md`)
- Phase 1+ 가 곧장 코드 작성에 들어가려면, 그전에 모듈 경계·의존성·테스트 인프라가 미리 깔려 있어야 한다.

**목적**
- Phase 0 은 **빈 껍데기 골격을 완성**한다 — 폴더 트리, `__init__.py` 들, 핵심 의존성 추가, 린트/테스트 설정, 통일된 `Settings` 진입점.
- 이후 Phase 들이 "어디에 무엇을 둘지 / 의존성이 깔려 있나 / env 어떻게 읽지" 를 더 이상 고민하지 않도록 만든다.
- 코드 본체(Protocol/ABC 시그니처·런타임 로직)는 **Phase 0 에 포함되지 않는다**. 그건 각 해당 Phase 의 책임.

---

## 2. 사용자 스토리 / 시나리오

- **US-1 (개발자, Phase 1 진입)** — 다음 Phase 시작 시 어느 폴더에 무엇을 만들지 고민 없이 곧장 코드 작성에 들어가고 싶다. **그래서** 모든 모듈 자리(`core/`, `prompts/`, `attachments/`, `tools/`, `hitl/`, `llm/`, `context/`, `api/`, `db/`)가 빈 껍데기로 미리 깔려 있길 원한다.

- **US-2 (개발자, 의존성·환경)** — 베이스 의존성이 이미 설치돼 있고 환경변수는 한 곳에서 읽어오길 원한다. **그래서** Phase 1+ 가 import 깨짐·env 누락으로 막히지 않는다.

- **US-3 (개발자, 품질 가드)** — `uv run pytest` / `uv run ruff` 한 번에 동작하는 최소 테스트·린트 인프라가 있길 원한다. **그래서** 빈 껍데기여도 import 무결성·기본 코딩 컨벤션이 검증돼 다음 Phase 가 안전.

- **US-4 (외부 개발자, 미래 시점)** — `from best_agent_base import ...` 로 시작했을 때 모듈 트리만 봐도 "여긴 무슨 책임" 이 자명하길 원한다. **그래서** 패키지 명명·디렉토리 분류가 직관적이어야 한다.

---

## 3. 기능 요구사항 (FR)

### FR-1 — 모듈 골격 디렉토리·파일
`best_agent_base/` 패키지 아래 다음 9개 서브패키지 디렉토리가 생성되고, 각각 빈 `__init__.py` 를 포함한다:

```
best_agent_base/
├── core/__init__.py
├── prompts/__init__.py
├── attachments/__init__.py
├── tools/__init__.py
├── hitl/__init__.py
├── llm/__init__.py            (이미 존재 — gemini.py 유지)
├── context/__init__.py
├── api/__init__.py
└── db/__init__.py
```

### FR-2 — 베이스 의존성
`pyproject.toml` 에 다음 의존성이 명시되어 있고, `uv sync` 로 설치된다:

- 런타임: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic-settings`, `tiktoken` (그리고 기존 `langgraph`, `langchain-google-genai`, `python-dotenv`)
- 개발(dev group): `pytest`, `pytest-asyncio`, `ruff`

### FR-3 — Settings 진입점
`best_agent_base/config.py` 에 `Settings(BaseSettings)` 클래스가 정의된다. 최소 필드:

| 필드 | 타입 | 기본값 |
|---|---|---|
| `google_api_key` | `str` | (필수, 누락 시 ValidationError) |
| `log_level` | `str` | `"INFO"` |
| `database_url` | `str` | `"postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base"` (호스트 포트 5435 — 로컬 dev docker-compose 와 정렬, FR-7 참조) |
| `agent_state_dir` | `str` | `"./.agent_state"` (경로 문자열만, **휘발 캐시 시맨틱** — 디렉토리 자동 생성·삭제 가능, 영속이 필요한 데이터는 절대 여기 두지 않음. Cache/BlobStore Protocol 본체는 Phase 9 책임) |
| `redis_url` | `str \| None` | `None` (있으면 EphemeralCache 백엔드 자동 전환 — Phase 9) |
| `blob_store_url` | `str \| None` | `None` (있으면 BlobStore 백엔드 자동 전환 — Phase 9) |

`SettingsConfigDict(env_file=".env", extra="ignore")` 사용.

### FR-4 — 린트 설정
`pyproject.toml [tool.ruff]` 에 다음이 명시되어 있다:

- `line-length` (예: 100)
- `target-version = "py312"`
- 기본 룰셋 (E, F, I 최소)

### FR-5 — 테스트 인프라
- `pyproject.toml [tool.pytest.ini_options]` 에 `testpaths = ["tests"]`, `asyncio_mode = "auto"` 명시.
- `tests/` 디렉토리 + `tests/test_smoke.py` 1개 파일 존재.
- `test_smoke.py` 는 9개 서브패키지 + `config` 의 import 무결성을 검증한다.

### FR-6 — Import 무결성
다음 한 줄이 인터프리터에서 무에러 동작한다:

```python
from best_agent_base import core, prompts, attachments, tools, hitl, llm, context, api, db, config
```

### FR-7 — 로컬 개발 인프라 (Docker Compose)
프로젝트 루트에 `docker-compose.yml` 이 존재하고, 다음 서비스를 부팅한다:

- **postgres** (image: `postgres:16-alpine`) — 호스트 포트 **5435** → 컨테이너 5432, DB `best_agent_base`, 볼륨 영속화, healthcheck
- **redis** (image: `redis:7-alpine`) — 호스트 포트 **6379**, 볼륨 영속화, healthcheck

`.env.example` 의 `DATABASE_URL` 디폴트도 호스트 5435 와 정렬. 사용법은 `docs/local-dev-setup.md` 참조.

> 포트 5435 사용 이유: 사용자 환경에 기존 Postgres(5432) 가 이미 동작 중. 충돌 회피.

---

## 4. 비기능 요구사항 (NFR)

### NFR-1 — 재현성
`uv.lock` 이 git 에 커밋되어 어느 머신에서도 `uv sync` 로 동일 환경 복제 가능.

### NFR-2 — 보안 (시크릿 누설 방지)
`.gitignore` 에 다음이 모두 포함:
- `.env`, `.env.local`, `.env.*.local`
- `.venv`, `.worktrees/`, `.vscode/`, `.idea/`, `.DS_Store`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `htmlcov/`

`.env.example` 만 커밋 (값은 빈 placeholder 또는 비프로덕션 키만).

### NFR-3 — 유지보수성 (린트)
`uv run ruff check .` 가 모든 신규/기존 파일에 대해 exit 0.

### NFR-4 — 확장성 (모듈 경계)
9개 서브패키지가 단일 책임으로 분리되어, Phase 1+ 가 다른 모듈 건드리지 않고 단일 패키지에서 작업 가능.

### NFR-5 — 성능
**없음** (Phase 0 은 런타임 코드 무. 성능 측정·튜닝은 Phase 11(Hooks) 이후 본격화).

### NFR-6 — 가용성·SLA
**없음** (API 노출은 Phase 14(FastAPI) 시점부터).

---

## 5. 범위 밖 (Out of Scope)

대화 중 명시된 제외 항목 통합:

- **모든 Protocol/ABC 본체** — `Tool`, `Permission`, `Hook`, `Memory`, `Subagent`, `AttachmentCollector` 등의 시그니처/추상 정의는 Phase 0 에서 하지 않는다. 해당 Phase(4, 8, 11, 12, 13)에서.
- **런타임 동작 코드** — ReAct 루프, 어태치먼트 수집, 캐싱 로직, 도구 실행 파이프라인 등 본체 코드는 전부 Phase 1+ 로 이연. Phase 0 의 `__init__.py` 들은 비어 있다.
- **도구 호출 병렬/순차 디스패처** — Phase 5.
- **Phase 10 도구 실행 파이프라인의 도메인-특화 분류기 본체** — 다른(도메인) 프로젝트 책임.
- **성능 측정·튜닝** — Phase 11(Hooks) 이후.
- **API 가용성·SLA** — Phase 14(FastAPI) 시점부터.
- **Skills / Slash command 레지스트리** — TODO.md 전체 Out of scope.
- **풀 MCP 클라이언트** — 동일.
- **React/Ink TUI 컴포넌트** — 동일 (CC 의 프론트엔드 영역).
- **GrowthBook 류 피처 플래그 인프라** — 동일.
- **분산 task queue** — 동일.

---

## 6. 수용 기준 (Acceptance Criteria)

- **AC-1** — `best_agent_base/` 아래 9개 서브패키지(`core`, `prompts`, `attachments`, `tools`, `hitl`, `llm`, `context`, `api`, `db`) 디렉토리 + 각 빈 `__init__.py` 존재. (`ls best_agent_base/*/__init__.py` 9개 출력)
- **AC-2** — `pyproject.toml` 의 `[project.dependencies]` 와 dev group 에 FR-2 목록 모두 포함. (grep / `uv tree` 확인)
- **AC-3** — `uv sync` exit 0.
- **AC-4** — `Settings()` 호출 시 `GOOGLE_API_KEY` 누락이면 pydantic `ValidationError` 발생. (단위 테스트)
- **AC-5** — `Settings()` 의 우선순위가 **init 인자 > OS 환경변수 > .env > 기본값** 이다. (단위 테스트)
- **AC-6** — `uv run ruff check .` exit 0.
- **AC-7** — `uv run pytest` exit 0.
- **AC-8** — `tests/test_smoke.py` 가 9개 서브패키지 + `config` 모두를 import 하고 통과.
- **AC-9** — `from best_agent_base import core, prompts, attachments, tools, hitl, llm, context, api, db, config` 한 줄이 인터프리터에서 무에러 동작.
- **AC-10** — `git status` 시 `.env` 가 untracked·ignored 로 표시되어 staged 되지 않는다.
- **AC-11** — `docker compose up -d` 후 `docker compose ps` 에서 postgres/redis 둘 다 `(healthy)` 상태 표시. (FR-7)
- **AC-12** — `psql postgresql://postgres:postgres@localhost:5435/best_agent_base -c "SELECT 1"` exit 0. (FR-7)
- **AC-13** — `redis-cli -p 6379 ping` 응답 `PONG`. (FR-7)

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 09:15] [요구사항-수정]
- **id**: CH-20260503-001
- **이유**: 신규 피처 brainstorming 결과 (Phase 0 — 프로젝트 골격 PRD 최초 작성)
- **무엇이**: phase-0-skeleton-requirements.md 전체 (US-1..US-4, FR-1..FR-6, NFR-1..NFR-6, OOS 11개, AC-1..AC-10)
- **영향범위**: 없음 (최초 생성)

### [2026-05-03 10:30] [요구사항-수정]
- **id**: CH-20260503-002
- **이유**: designing-direction 단계에서 (1) DB = Postgres + asyncpg 결정, (2) 2-Tier 저장 모델(영속 DB + 휘발 캐시 Protocol 슬롯) 채택, (3) 로컬 dev 인프라 = docker-compose(host port 5435) 채택. PRD 가 디자인 결정과 일관되어야 하므로 cascade 갱신.
- **무엇이**:
  - FR-3 의 `database_url` 디폴트: `sqlite:///./agent.db` → `postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base`
  - FR-3 의 `agent_state_dir` 시맨틱 명시: 휘발 캐시 (영속 데이터 금지)
  - FR-3 에 `redis_url`, `blob_store_url` Optional 필드 신규 추가
  - **FR-7 신설**: 로컬 개발 인프라 (docker-compose.yml — postgres host 5435, redis 6379)
  - AC-11/12/13 신규 추가 (FR-7 검증)
- **영향범위**: 본 PRD 의 FR-3 / 신규 FR-7 / 신규 AC-11~13 + 곧 작성될 phase-0-skeleton-tech-design.md (D-1, D-2, D-3, D-11) + docs/local-dev-setup.md (이미 작성됨)
- **연관 항목**: (tech-design 의 첫 CH 엔트리에서 cross-link 예정)
