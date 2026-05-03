# 개발방향: Phase 0 — 프로젝트 골격 (phase-0-skeleton)

> **For agentic workers:** This document is the technical spec (architecture, components, data, interfaces, decisions, risks, test strategy). It is anchored to `phase-0-skeleton-requirements.md` (the PRD) and consumed by `phase-0-skeleton-implementation-plan.md` (step-by-step plan). NEXT STEP: invoke `writing-plans` skill (or run `/write-plan`) to produce `phase-0-skeleton-implementation-plan.md` from this design. Do NOT include step-by-step implementation tasks here — those belong in the plan.

---

## 1. 아키텍처 개요

Phase 0 은 **순수 스캐폴드 단계** — 런타임 로직 없음, 모듈 토폴로지·의존성·설정·테스트 인프라만 마련. 본 베이스(전 14 Phase) 의 모든 후속 Phase 가 곧장 코드 작성에 들어갈 수 있도록 "어디에 무엇을 둘지" 를 사전에 결정한다.

### 채택: Flat 9-package layout (대안 A)

```
best_agent_base/
├── __init__.py
├── config.py                 # pydantic-settings 기반 Settings 진입점
├── core/         __init__.py # 하네스 · 세션 · ReAct 루프 (Phase 5)
├── prompts/      __init__.py # 시스템 프롬프트 정적/동적 분리 (Phase 1)
├── attachments/  __init__.py # 이중 어태치먼트 시스템 (Phase 3)
├── tools/        __init__.py # 도구 베이스 + 빌트인 + ToolSearch (Phase 4, 6)
├── hitl/         __init__.py # 권한 + 비동기 대기 (Phase 8)
├── llm/          __init__.py # 모델 어댑터 (현재 Gemini)
├── context/      __init__.py # 컨텍스트 관리·캐시·블롭 Protocol (Phase 9)
├── api/          __init__.py # FastAPI (Phase 14)
└── db/           __init__.py # SQLAlchemy 모델 (Phase 9·11·14)

tests/            __init__.py
├── test_smoke.py             # 9개 서브패키지 import 무결성
└── test_settings.py          # Settings 우선순위 + ValidationError

scripts/
└── change_id.py              # js-super:change-history 헬퍼 (이미 존재)

docker-compose.yml            # postgres(5435) + redis(6379)
pyproject.toml                # deps + ruff + pytest 설정
.env.example                  # GOOGLE_API_KEY, DATABASE_URL(5435), 옵셔널 REDIS_URL/BLOB_STORE_URL
```

**왜 flat (대안 B 의 tiered runtime/transport/persistence 거부)**
- TODO.md 1:1 일관성
- 도메인-중립 명명 유지 (`runtime`, `transport`, `persistence` 같은 분류명은 코드 도메인 어휘로 해석될 여지가 있어 베이스 목적과 충돌)
- 모듈 1개 작업 시 import 깊이 +1 단 비용 회피
- SRP 강제력 동일 (디렉토리 단위로 책임 분리)
- 단점인 "9개" 가독성은 `__init__.py` 한 줄 docstring 으로 보강

---

## 2. 영향 받는 컴포넌트 / 파일

### FR → 파일 매핑

| FR | 신규/수정 파일 | 비고 |
|---|---|---|
| **FR-1** 모듈 골격 | `best_agent_base/{core,prompts,attachments,tools,hitl,context,api,db}/__init__.py` (신규 8개), `best_agent_base/llm/__init__.py` (기존 유지), `best_agent_base/__init__.py` (기존 유지·docstring 보강) | 빈 `__init__.py` + 한 줄 docstring (책임) |
| **FR-2** 베이스 의존성 | `pyproject.toml` (`[project.dependencies]`, `[dependency-groups.dev]`) | `uv add` 로 갱신 |
| **FR-3** Settings 진입점 | `best_agent_base/config.py` (신규) | `BaseSettings` 상속, 6 필드 (필수 1 + 옵셔널 5) |
| **FR-4** 린트 설정 | `pyproject.toml [tool.ruff]` | line-length=100, target-version=py312, select=["E","F","I"] 보수적 시작 |
| **FR-5** 테스트 인프라 | `pyproject.toml [tool.pytest.ini_options]`, `tests/__init__.py`, `tests/test_smoke.py`, `tests/test_settings.py` | testpaths=["tests"], asyncio_mode="auto" |
| **FR-6** Import 무결성 | `tests/test_smoke.py` 가 검증 | 9 패키지 + config 임포트 |
| **FR-7** 로컬 dev 인프라 | `docker-compose.yml` (신규), `.env.example` 갱신, `README.md` Setup 섹션 보강 | postgres host 5435, redis 6379, healthcheck, named volumes |

### 부수 산출

- 각 신규 `__init__.py` 의 한 줄 docstring (예: `"""Tool abstraction, registry, search, builtins."""`)
- `README.md` 에 `docker compose up -d` 단계 추가, `pip install` 대체 안내
- `docs/local-dev-setup.md` (이미 작성됨)

---

## 3. 데이터 모델 / 스키마 변경

**Phase 0 단계: 스키마 정의·생성 없음.**

- DB 모델 정의 / Alembic 마이그레이션 → Phase 9·11·14
- `db/__init__.py` 디렉토리만 신설하여 Phase 9 가 즉시 들어갈 자리 마련
- `Settings.database_url` 만 정의 (연결 안 함, 검증 안 함)

### 2-Tier 저장 모델 (참조 — Phase 9 가 본체 구현)

| Tier | 위치 | 백엔드 | 들어가는 것 |
|---|---|---|---|
| **Tier 2 — 영속** | `DATABASE_URL` (Postgres) | SQLAlchemy 2.x async + asyncpg | 세션·턴·도구호출 레저, 4타입 메모리, 핸드오프 문서, 태스크/투두 |
| **Tier 1a — 휘발 KV 캐시** | `EphemeralCache` Protocol (Phase 9) | 디폴트 FS (`AGENT_STATE_DIR/cache`), 옵셔널 Redis (`REDIS_URL`) | 컴팩션 스냅샷, 세션 스크래치, 토큰 카운트 캐시 |
| **Tier 1b — 휘발 블롭** | `BlobStore` Protocol (Phase 9) | 디폴트 FS (`AGENT_STATE_DIR/blobs`), 옵셔널 S3 (`BLOB_STORE_URL`) | 큰 도구 결과 dump, 큰 어태치먼트 본문 |

**시맨틱 룰**: Tier 1 (a/b 모두) 은 *언제든 사라져도 시스템 정상 동작* 해야 함.

---

## 4. 외부 인터페이스

| 종류 | Phase 0 노출 | 비고 |
|---|---|---|
| HTTP API | 없음 | Phase 14 |
| CLI | 없음 | OOS |
| **환경변수 / `.env`** (Settings 입력) | `GOOGLE_API_KEY` (필수), `LOG_LEVEL`, `DATABASE_URL`, `AGENT_STATE_DIR`, `REDIS_URL` (Optional), `BLOB_STORE_URL` (Optional) | pydantic-settings 의 `env_file=".env"`, `extra="ignore"` |
| **Docker Compose 서비스** | `bab_postgres` (host 5435), `bab_redis` (6379) | healthcheck 포함, 외부에서 `psql`/`redis-cli` 로 접속 가능 |
| **Python import surface** | `from best_agent_base import {core,prompts,attachments,tools,hitl,llm,context,api,db,config}` | 각 서브패키지 내부 심볼은 Phase별 노출 (Phase 0 은 빈 모듈) |
| 이벤트 / pub-sub | 없음 | Phase 11 (Hooks) / Phase 12 (Subagent) 이후 |

---

## 5. 핵심 결정 + 대안 비교

| # | 결정 | 대안 | 채택 이유 |
|---|---|---|---|
| **D-1** | DB 드라이버 = `asyncpg` + SQLAlchemy 2.x async | (a) psycopg[binary] async+sync / (b) psycopg2 sync only | FastAPI 백엔드 베이스라 비동기 우선; psycopg2 는 이벤트 루프 블록 / asyncpg 가 비동기 성능 가장 우수 |
| **D-2** | **2-Tier 저장 모델 + 캐시 Protocol 슬롯**: Postgres(영속) + EphemeralCache + BlobStore (둘 다 Protocol) | (a) 단일 FS — 백엔드 wipe 위험 / (b) 단일 DB — 큰 결과 dump 비효율 / (c) AGENT_STATE_DIR 단일 슬롯 — 작은 KV 와 큰 블롭 백엔드 적합도가 달라 통합 비효율 | 책임 분리 + Open/Closed (원칙 #8). 디폴트 FS, 프로덕션 Redis/S3 자동 교체 |
| **D-3** | AGENT_STATE_DIR = 휘발 캐시 시맨틱 ("사라져도 정상 동작") | persistent FS 로 유지 | 컨테이너 재시작·다중 인스턴스·오토스케일 시 깨짐 회피 |
| **D-4** | 테스트 DB = sqlite+aiosqlite(단위) + Postgres(통합) | (a) Postgres만 — 단위 느림 / (b) sqlite만 — 방언 차이 | 단위 빠름 + 핵심 통합만 정확성 |
| **D-5** | 마이그레이션 = Alembic (sync 모드, 별도 sync URL) | None / 직접 SQL | Alembic 표준; sync 모드는 마이그레이션이 IO 블로킹이라 오히려 적합 |
| **D-6** | 린트 = ruff (formatter + linter 통합) | black + flake8 + isort | 단일 도구 대체, 속도↑ |
| **D-7** | 테스트 = pytest + pytest-asyncio (`asyncio_mode="auto"`) | unittest / asynctest | 표준, 데코레이터 없이 async 동작 |
| **D-8** | Settings = pydantic-settings (`SettingsConfigDict(env_file=".env", extra="ignore")`) | os.environ / dynaconf / hydra | 타입 안정 + .env 통합 + 우선순위 자동 |
| **D-9** | 폴더 토폴로지 = Flat 9-package | Tiered (runtime/transport/persistence) | TODO.md 1:1, 도메인-중립 명명, SRP |
| **D-10** | PRD/TODO cascade 처리 | 디자인만 변경 — 일관성 깨짐 | change-history cross-link 으로 정합성 유지 (CH-20260503-002 이미 박음) |
| **D-11** | 로컬 dev 인프라 = docker-compose (postgres host **5435** + redis 6379) | (a) 호스트 직접 설치 — 환경 오염 / (b) 5432 사용 — 사용자 기존 DB 와 충돌 | 사용자 환경에 5432 점유 중 → 5435 채택. healthcheck + named volume 으로 데이터 영속화 |
| **D-12** | Settings 인스턴스화는 lazy (모듈 레벨 인스턴스화 금지) | 모듈 레벨 글로벌 instance | 환경 누락된 CI/테스트에서 import 자체가 깨지는 사고 방지 (R-4 회피) |
| **D-13** | `__init__.py` 빈 상태 + 한 줄 docstring 만 (모듈 레벨 IO/네트워크 절대 금지) | 편의 import / 자동 등록 로직 | 무거운 import side-effect 회피 (R-5), 테스트 부팅 속도 보장 |

---

## 6. 위험 / 사이드이펙트 (preliminary)

| ID | 위험 | 카테고리 | 완화책 |
|---|---|---|---|
| **R-1** | `pyproject.toml` 의존성 추가 시 기존 langchain/langgraph 와 버전 충돌 | breaking | `uv add` 시 lockfile 결정성 + 추가 직후 import smoke 테스트 |
| **R-2** | ruff 룰셋이 기존 코드와 충돌 | breaking | 보수적 룰셋(E/F/I)으로 시작, 기존 코드 한 번 정리 후 통과 |
| **R-3** | Python 3.12 강제 — 다른 머신 3.11 → 부팅 실패 | breaking | `.python-version` + README 명시 |
| **R-4** | `Settings()` 모듈 레벨 인스턴스화 시 `GOOGLE_API_KEY` 누락 환경에서 import 깨짐 | side-effect | **D-12 — lazy 인스턴스화 룰**. test_settings.py 가 패턴 검증 |
| **R-5** | smoke 테스트가 9 서브패키지 import — 향후 모듈 레벨 IO 로 부팅 느려짐 | perf | **D-13 — `__init__.py` 빈 상태 룰** Phase 1+ 에도 강제 |
| **R-6** | AGENT_STATE_DIR 경로 부재 시 후속 Phase 가 무관심하게 사용 → FileNotFoundError | side-effect | Phase 9 첫 사용 시점에 `mkdir(parents=True, exist_ok=True)` 책임 (Phase 0 OOS) |
| **R-7** | DATABASE_URL 디폴트 (5435) 가 CI 에 Postgres 없이 돌면 연결 실패 | side-effect | Phase 0 시점은 **연결 안 함** (Settings 만 정의). 단위 테스트는 sqlite (D-4) |
| **R-8** | langchain 메이저 업그레이드 진행 중 추가 의존성 충돌 가능성 | breaking | langchain 버전 핀 그대로 유지 (메이저 업그레이드 별도 Phase) |
| **R-9** | `.env` 의 실제 키가 `.env.example` 에 잘못 들어가 git 노출 | side-effect | `.env.example` 빈 placeholder 유지, Phase 0 종료 전 `git diff` 점검 |
| **R-10** | docker-compose 의 호스트 5435 가 다른 프로젝트와 또 충돌 | side-effect | `docs/local-dev-setup.md` 의 트러블 섹션에 충돌 진단 + 포트 변경 가이드 |
| **R-11** | 컨테이너 이름 `bab_postgres`/`bab_redis` 가 다른 프로젝트와 충돌 | side-effect | 충돌 시 `docker rm` 안내 (local-dev-setup.md 트러블 섹션) |

---

## 7. 테스트 전략

### 단위 (Phase 0 범위)

| 파일 | 검증 항목 | 매핑 |
|---|---|---|
| `tests/test_smoke.py` | 9 서브패키지 + `config` import 무에러 | AC-8, AC-9, FR-6 |
| `tests/test_settings.py` | (1) 필수 필드 누락 → `ValidationError` / (2) 우선순위(init > env > .env > default) / (3) `.env` 로딩 정상 | AC-4, AC-5, FR-3, D-12 (lazy 인스턴스화 패턴 동시 검증) |

### 통합

**Phase 0 범위 외**. DB·API 코드 미존재. (Phase 9·14 시점부터)

### API 자동 테스트 (`/api-test`)

**스킵** — Phase 0 은 API 노출 없음 (TODO.md 의 명시 스킵 조건 해당).

### 인프라 검증 (FR-7)

수동 검증 절차 (CI 에 자동화 안 함 — Docker 가용성 의존):

```bash
docker compose up -d
docker compose ps                          # AC-11: 둘 다 (healthy)
psql postgresql://postgres:postgres@localhost:5435/best_agent_base -c "SELECT 1"  # AC-12
redis-cli -p 6379 ping                     # AC-13
```

### 린트

`uv run ruff check .` exit 0 (AC-6). pre-commit 훅화는 **OOS** (개발자 자율).

### 재현성 (NFR-1)

`uv sync` 실행 후 생성/갱신된 `uv.lock` 은 **git 커밋 필수** — 어느 머신에서도 동일 환경 복제. PR 시 lockfile 변동분 검토. (이미 초기 부트스트랩 커밋에 `uv.lock` 포함됨, 향후 `uv add` 마다 재커밋 필요.)

### 테스트 환경

- `uv run pytest` 한 번에 단위 전부 실행
- DB-의존 테스트 없음 → docker 미가용 환경에서도 단위 통과 보장
- `aiosqlite` 는 dev dep 으로 추가하지만 Phase 0 단위 테스트에선 미사용 (Phase 9 부터)

### 커버리지

Phase 0 인프라가 작아 커버리지 측정 의미 낮음 — 두 테스트 파일 통과면 충분. Phase 9 부터 커버리지 도입.

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 11:10] [개발방향-수정]
- **id**: CH-20260503-003
- **이유**: 신규 기술 설계 (Phase 0 — 프로젝트 골격 tech-design 최초 작성). designing-direction 7 단계 질의(Q1~Q7) 합의 결과를 §1~§7 로 구조화. verifying-spec 1차 → NFR-1 매핑 추가 → 재검증 통과.
- **무엇이**: phase-0-skeleton-tech-design.md 전체 (§1 아키텍처 / §2 컴포넌트 매핑 / §3 데이터 모델 / §4 외부 IF / §5 결정 D-1~D-13 / §6 위험 R-1~R-11 / §7 테스트 전략 + 재현성)
- **영향범위**: phase-0-skeleton-requirements.md 와 정합 (cascade 갱신은 CH-20260503-002 에서 선처리). 후속 phase-0-skeleton-implementation-plan.md 의 task 분해가 §5 결정·§6 위험·§7 테스트를 기반으로 작성될 것.
- **연관 항목**: CH-20260503-002 (PRD cascade — Postgres/2-Tier/docker-compose 결정의 PRD 측 반영)
- **verify 결과**: A. Consistency 21 mapped / 0 gaps / 0 conflicts. C. Impact 13 파일(신규 10·수정 5), 위험 11개 모두 mitigation, AC 100% 테스트 매핑.
