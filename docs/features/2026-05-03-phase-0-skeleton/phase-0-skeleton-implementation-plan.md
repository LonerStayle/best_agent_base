# Phase 0 — 프로젝트 골격 구현계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1+ 가 곧장 코드 작성에 들어갈 수 있는 빈 껍데기 골격 — 9 서브패키지 + 베이스 의존성 + Settings + 린트/테스트 인프라 + 로컬 dev (Postgres 5435 + Redis) — 을 구축하고 13 AC 모두 통과.

**Architecture:** Flat 9-package layout(`core/prompts/attachments/tools/hitl/llm/context/api/db` + `config.py`). 2-Tier 저장(영속 Postgres + 휘발 캐시 Protocol 슬롯, 본체는 Phase 9). pydantic-settings 기반 단일 Settings 진입점. 런타임 코드 무, 추상 본체 무 — 순수 스캐폴드.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2.x async + asyncpg, pydantic-settings, ruff, pytest + pytest-asyncio, Docker Compose (Postgres 16 + Redis 7).

**Spec inputs:**
- `phase-0-skeleton-requirements.md` — FR-1..FR-7, NFR-1..NFR-6, AC-1..AC-13
- `phase-0-skeleton-tech-design.md` — D-1..D-13, R-1..R-11, §7 테스트 전략

---

## 1. 단계별 작업

### Task 1: 베이스 런타임 의존성 추가

**Files:**
- Modify: `pyproject.toml` (의존성 섹션, `uv` 가 자동 갱신)
- Modify: `uv.lock` (자동)

매핑: FR-2, AC-2, AC-3, R-1 (mitigation), D-1, D-5

- [ ] **Step 1: 현재 의존성 스냅샷 (이전 상태 기록)**

```bash
grep -A 20 '\[project\]' pyproject.toml
uv tree --depth 1 | head -30
```

- [ ] **Step 2: 베이스 런타임 deps 추가**

```bash
uv add fastapi uvicorn 'sqlalchemy[asyncio]' asyncpg alembic pydantic-settings tiktoken
```

- [ ] **Step 3: 설치 검증**

Run:
```bash
uv sync
```
Expected: exit 0, "Resolved/Installed N packages" 출력.

- [ ] **Step 4: import smoke (수동 1회)**

```bash
uv run python -c "import fastapi, sqlalchemy, asyncpg, alembic, pydantic_settings, tiktoken; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add base runtime deps (fastapi, sqlalchemy[asyncio]+asyncpg, alembic, pydantic-settings, tiktoken)"
```

---

### Task 2: 개발 의존성 추가

**Files:**
- Modify: `pyproject.toml` (`[dependency-groups]` dev)
- Modify: `uv.lock`

매핑: FR-2, FR-5, D-4, D-6, D-7

- [ ] **Step 1: dev deps 추가**

```bash
uv add --dev pytest pytest-asyncio ruff aiosqlite
```

- [ ] **Step 2: 설치 검증**

Run:
```bash
uv sync && uv run pytest --version && uv run ruff --version
```
Expected: pytest 8.x, ruff 0.x 버전 출력.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add dev deps (pytest, pytest-asyncio, ruff, aiosqlite)"
```

---

### Task 3: ruff 설정 추가

**Files:**
- Modify: `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`)

매핑: FR-4, AC-6, R-2 (mitigation), D-6

- [ ] **Step 1: pyproject.toml 끝부분에 설정 추가**

다음 블록을 `pyproject.toml` 마지막에 append:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 2: 기존 코드에 ruff 적용 (자동 픽스 + 잔여 확인)**

Run:
```bash
uv run ruff check . --fix
uv run ruff check .
```
Expected: 두 번째 명령 exit 0, "All checks passed!" 출력.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml best_agent_base/ main.py
git commit -m "chore(lint): configure ruff (line-length 100, py312, E/F/I rules)"
```

---

### Task 4: pytest 설정 추가

**Files:**
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`)

매핑: FR-5, AC-7, D-7

- [ ] **Step 1: pyproject.toml 에 pytest 설정 append**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: pytest 부팅 확인 (테스트 0개라도 정상 종료)**

Run:
```bash
uv run pytest
```
Expected: `no tests ran in ...s` 또는 exit 5 (no tests collected) — 둘 다 OK 판정 (다음 Task 에서 테스트 추가).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(test): configure pytest (testpaths=tests, asyncio_mode=auto)"
```

---

### Task 5: 스모크 테스트 작성 (RED)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

매핑: FR-6, AC-8, AC-9, R-5 (mitigation 검증)

- [ ] **Step 1: tests/ 디렉토리 + 빈 __init__.py 생성**

```bash
mkdir -p tests
```

`tests/__init__.py` (빈 파일):
```python
```

- [ ] **Step 2: 실패할 스모크 테스트 작성**

`tests/test_smoke.py`:
```python
"""Phase 0 import 무결성 스모크 테스트.

9개 서브패키지 + config 가 모두 import 가능해야 한다.
"""

import importlib

import pytest

SUBPACKAGES = [
    "best_agent_base.core",
    "best_agent_base.prompts",
    "best_agent_base.attachments",
    "best_agent_base.tools",
    "best_agent_base.hitl",
    "best_agent_base.llm",
    "best_agent_base.context",
    "best_agent_base.api",
    "best_agent_base.db",
    "best_agent_base.config",
]


@pytest.mark.parametrize("module_name", SUBPACKAGES)
def test_subpackage_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_top_level_aggregate_import() -> None:
    from best_agent_base import (  # noqa: F401
        api,
        attachments,
        config,
        context,
        core,
        db,
        hitl,
        llm,
        prompts,
        tools,
    )
```

- [ ] **Step 3: 테스트 실행 — RED 확인**

Run:
```bash
uv run pytest tests/test_smoke.py -v
```
Expected: 다수 FAIL (`ModuleNotFoundError: No module named 'best_agent_base.core'` 등). `best_agent_base.llm` 만 통과.

- [ ] **Step 4: Commit (RED 상태 보존)**

```bash
git add tests/
git commit -m "test(smoke): add subpackage import integrity test (RED)"
```

---

### Task 6: 9 서브패키지 + docstring 생성 (GREEN)

**Files:**
- Create: `best_agent_base/core/__init__.py`
- Create: `best_agent_base/prompts/__init__.py`
- Create: `best_agent_base/attachments/__init__.py`
- Create: `best_agent_base/tools/__init__.py`
- Create: `best_agent_base/hitl/__init__.py`
- Create: `best_agent_base/context/__init__.py`
- Create: `best_agent_base/api/__init__.py`
- Create: `best_agent_base/db/__init__.py`
- Create: `best_agent_base/config.py` (스모크용 placeholder, 본체는 Task 8)

매핑: FR-1, AC-1, AC-9, D-9, D-13 (모듈 레벨 IO/네트워크 금지)

- [ ] **Step 1: 8개 서브패키지 디렉토리 + 빈 __init__.py 생성 (한 줄 docstring)**

각 파일 내용 (책임 한 줄 docstring + `pass` 선언 없음, 빈 모듈):

`best_agent_base/core/__init__.py`:
```python
"""Harness · session · ReAct loop (Phase 5)."""
```

`best_agent_base/prompts/__init__.py`:
```python
"""System prompt static/dynamic separation (Phase 1)."""
```

`best_agent_base/attachments/__init__.py`:
```python
"""Dual attachment system — user input + ReAct round (Phase 3)."""
```

`best_agent_base/tools/__init__.py`:
```python
"""Tool base, registry, search, builtins (Phase 4, 6)."""
```

`best_agent_base/hitl/__init__.py`:
```python
"""Human-in-the-loop — permissions + async waiter (Phase 8)."""
```

`best_agent_base/context/__init__.py`:
```python
"""Context management — compaction, EphemeralCache, BlobStore Protocols (Phase 9)."""
```

`best_agent_base/api/__init__.py`:
```python
"""FastAPI endpoints (Phase 14)."""
```

`best_agent_base/db/__init__.py`:
```python
"""SQLAlchemy models · session — Tier 2 영속 (Phase 9·11·14)."""
```

- [ ] **Step 2: config.py 임시 placeholder 생성 (Task 8 에서 본체 작성)**

`best_agent_base/config.py`:
```python
"""Settings entrypoint — pydantic-settings based (Task 8 에서 본체 작성)."""
```

- [ ] **Step 3: 스모크 테스트 실행 — GREEN 확인**

Run:
```bash
uv run pytest tests/test_smoke.py -v
```
Expected: 11 passed (9 서브패키지 parametrized + 1 aggregate + llm 포함)

- [ ] **Step 4: 모듈 레벨 IO 룰 점검 (D-13)**

Grep 으로 새 __init__.py 들이 빈 docstring 만 있는지 확인:
```bash
for f in best_agent_base/{core,prompts,attachments,tools,hitl,context,api,db}/__init__.py; do
  echo "--- $f ---"
  cat "$f"
done
```
Expected: 각 파일이 docstring 1 줄 만. import/IO/network 호출 없음.

- [ ] **Step 5: Commit (GREEN)**

```bash
git add best_agent_base/
git commit -m "feat(skeleton): create 9 subpackages + config placeholder (smoke GREEN)"
```

---

### Task 7: Settings 단위 테스트 작성 (RED)

**Files:**
- Create: `tests/test_settings.py`

매핑: FR-3, AC-4, AC-5, D-8, D-12 (lazy 인스턴스화 패턴 동시 검증)

- [ ] **Step 1: 실패할 Settings 테스트 작성**

`tests/test_settings.py`:
```python
"""Settings 단위 테스트 — pydantic-settings 기반.

검증 항목:
- (T1) GOOGLE_API_KEY 누락 시 ValidationError
- (T2) 우선순위: init > OS env > .env > 기본값
- (T3) .env 파일 로딩 정상
- (T4) 모듈 레벨 instance 가 없는지 (lazy 인스턴스화 룰 — D-12)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


def _fresh_import(monkeypatch, env: dict[str, str | None], cwd: Path | None = None):
    """깨끗한 환경에서 best_agent_base.config 재import.

    - 기존 환경변수 모두 제거 후 env 로 덮어씀 (None 인 키는 명시적 삭제)
    - sys.modules 에서 config 제거 → reload
    """
    for key in ("GOOGLE_API_KEY", "LOG_LEVEL", "DATABASE_URL", "AGENT_STATE_DIR", "REDIS_URL", "BLOB_STORE_URL"):
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    if cwd is not None:
        monkeypatch.chdir(cwd)
    sys.modules.pop("best_agent_base.config", None)
    return importlib.import_module("best_agent_base.config")


def test_missing_required_field_raises(monkeypatch):
    """T1: GOOGLE_API_KEY 누락 + .env 없으면 ValidationError."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None}, cwd=Path("/tmp"))
    with pytest.raises(ValidationError):
        mod.Settings()


def test_init_arg_overrides_env(monkeypatch):
    """T2-a: init 인자 > env."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "from-env"})
    settings = mod.Settings(google_api_key="from-init")
    assert settings.google_api_key == "from-init"


def test_env_overrides_default(monkeypatch):
    """T2-b: env > 기본값."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "k", "LOG_LEVEL": "DEBUG"})
    settings = mod.Settings()
    assert settings.log_level == "DEBUG"


def test_default_values_when_optional_missing(monkeypatch):
    """T2-c: 기본값 적용 (LOG_LEVEL 미지정 → INFO)."""
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": "k"})
    settings = mod.Settings()
    assert settings.log_level == "INFO"
    assert settings.agent_state_dir == "./.agent_state"
    assert settings.redis_url is None
    assert settings.blob_store_url is None
    assert "postgresql+asyncpg" in settings.database_url
    assert ":5435/" in settings.database_url


def test_dotenv_file_loaded(tmp_path, monkeypatch):
    """T3: .env 파일이 로드되어야 한다."""
    env_file = tmp_path / ".env"
    env_file.write_text("GOOGLE_API_KEY=from-dotenv\nLOG_LEVEL=WARNING\n")
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None, "LOG_LEVEL": None}, cwd=tmp_path)
    settings = mod.Settings()
    assert settings.google_api_key == "from-dotenv"
    assert settings.log_level == "WARNING"


def test_no_module_level_instance(monkeypatch):
    """T4: D-12 lazy 인스턴스화 룰 — 모듈 import 만으로는 Settings() 가 호출되지 않아야 한다.

    모듈 import 자체가 GOOGLE_API_KEY 누락 환경에서 깨지지 않는지 확인.
    """
    mod = _fresh_import(monkeypatch, env={"GOOGLE_API_KEY": None}, cwd=Path("/tmp"))
    # import 자체는 성공해야 함 (모듈 레벨 글로벌 인스턴스 없음)
    assert hasattr(mod, "Settings")
    # 모듈 attribute 에 settings 인스턴스가 글로벌로 존재하지 않음
    candidates = [name for name in dir(mod) if name.lower() in {"settings_instance", "config", "settings_global"}]
    assert candidates == [], f"모듈 레벨 글로벌 인스턴스 발견: {candidates}"
```

- [ ] **Step 2: 테스트 실행 — RED 확인**

Run:
```bash
uv run pytest tests/test_settings.py -v
```
Expected: 모두 FAIL (config.py 가 placeholder 라 `Settings` 클래스 없음).

- [ ] **Step 3: Commit (RED)**

```bash
git add tests/test_settings.py
git commit -m "test(settings): add Settings unit tests (RED — placeholder config)"
```

---

### Task 8: Settings 본체 구현 (GREEN)

**Files:**
- Modify: `best_agent_base/config.py` (placeholder → 본체)

매핑: FR-3, AC-4, AC-5, D-8, D-12

- [ ] **Step 1: config.py 본체 작성**

`best_agent_base/config.py` 전체 교체:
```python
"""Settings entrypoint — pydantic-settings based.

D-8: pydantic-settings 사용. 우선순위 = init 인자 > OS env > .env > 기본값.
D-12: 모듈 레벨에서 Settings() 인스턴스화 금지 (lazy). 호출 시점에 생성.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_api_key: str

    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base"
    )

    agent_state_dir: str = "./.agent_state"

    redis_url: str | None = None

    blob_store_url: str | None = None
```

- [ ] **Step 2: 테스트 실행 — GREEN 확인**

Run:
```bash
uv run pytest tests/test_settings.py -v
```
Expected: 6 passed.

- [ ] **Step 3: 전체 테스트 + 린트 회귀 확인**

Run:
```bash
uv run pytest && uv run ruff check .
```
Expected: 둘 다 exit 0.

- [ ] **Step 4: Commit (GREEN)**

```bash
git add best_agent_base/config.py
git commit -m "feat(config): implement Settings (BaseSettings, lazy, FS-cache + Postgres defaults)"
```

---

### Task 9: .env.example 갱신

**Files:**
- Modify: `.env.example`

매핑: FR-7, NFR-2, R-9 (mitigation), D-11

- [ ] **Step 1: 기존 .env.example 백업 확인**

```bash
cat .env.example
```
Expected: 기존 내용 (`GOOGLE_API_KEY=` 또는 placeholder)

- [ ] **Step 2: .env.example 전체 교체**

`.env.example`:
```bash
# Required
GOOGLE_API_KEY=

# Database — docker-compose.yml 의 postgres 서비스와 정렬 (host port 5435)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base

# Optional — 있으면 EphemeralCache 백엔드가 Redis 로 자동 전환 (Phase 9)
# REDIS_URL=redis://localhost:6379/0

# Optional — 있으면 BlobStore 가 S3 등 외부 객체 저장소로 자동 전환 (Phase 9)
# BLOB_STORE_URL=

# Misc
LOG_LEVEL=INFO
AGENT_STATE_DIR=./.agent_state
```

- [ ] **Step 3: 실제 키가 들어가지 않았는지 점검 (R-9 mitigation)**

```bash
grep -E '(AIza|sk-|key=[A-Za-z0-9])' .env.example && echo "WARNING: 실제 키 의심" || echo "ok"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add .env.example
git commit -m "chore(env): update .env.example (port 5435, REDIS_URL/BLOB_STORE_URL placeholders)"
```

---

### Task 10: docker-compose.yml 작성

**Files:**
- Create: `docker-compose.yml`

매핑: FR-7, AC-11, AC-12, AC-13, D-11, R-10/R-11 (mitigation은 docs/local-dev-setup.md 트러블 섹션)

- [ ] **Step 1: docker-compose.yml 생성**

`docker-compose.yml`:
```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: bab_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: best_agent_base
    ports:
      - "5435:5432"
    volumes:
      - bab_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: bab_redis
    ports:
      - "6379:6379"
    volumes:
      - bab_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  bab_postgres_data:
  bab_redis_data:
```

- [ ] **Step 2: 부팅 검증 (Docker Desktop 가동 중일 때)**

Run:
```bash
docker compose up -d
sleep 10
docker compose ps
```
Expected: `bab_postgres`, `bab_redis` 모두 `Up ... (healthy)` 상태.

- [ ] **Step 3: 접속 검증 (AC-12, AC-13)**

```bash
docker exec bab_postgres psql -U postgres -d best_agent_base -c "SELECT 1"
docker exec bab_redis redis-cli ping
```
Expected: PostgreSQL `1` 행 출력, Redis `PONG`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(infra): add docker-compose (postgres host 5435, redis 6379, healthchecks)"
```

---

### Task 11: README.md Setup 섹션 업데이트

**Files:**
- Modify: `README.md` (Setup 섹션)

매핑: FR-7 (사용자 진입성), R-3 (mitigation — Python 3.12 명시 재확인)

- [ ] **Step 1: README.md 의 Setup 섹션을 다음으로 교체**

`README.md` 의 `## Setup` 섹션 (`---` 으로 둘러싸인 블록) — 아래 내용 그대로 (외부 4-백틱 fence 는 본 plan 의 nested code block 회피용, 실제 README 에는 4-백틱 vs 3-백틱 안 들어감):

````markdown
## Setup

### 1. 의존성 설치

```bash
uv sync   # .venv 자동 생성 + 모든 deps 설치
```

> Python 3.12+ 필요. 현재 머신 버전 확인: `python --version`

### 2. 환경 변수

```bash
cp .env.example .env
# .env 에 GOOGLE_API_KEY 채움
```

### 3. 로컬 인프라 부팅 (Postgres + Redis)

```bash
docker compose up -d
docker compose ps   # 둘 다 (healthy) 확인
```

> Postgres 호스트 포트는 **5435** (5432 가 다른 프로젝트에 점유돼 있어 충돌 회피).
> 자세한 사용·접속·트러블슈팅은 [`docs/local-dev-setup.md`](docs/local-dev-setup.md) 참조.

### 4. 동작 확인

```bash
uv run pytest        # 테스트 통과
uv run ruff check .  # 린트 통과
uv run main.py       # Gemini 단일 노드 데모
```
````

- [ ] **Step 2: 시각 검증**

```bash
head -80 README.md
```
Expected: 위 섹션이 Setup 위치에 들어가 있음.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): expand Setup section (uv sync, .env, docker compose, verification)"
```

---

### Task 12: 최종 AC 전수 검증

**Files:** 없음 (검증만)

매핑: AC-1 ~ AC-13 전체

- [ ] **Step 1: AC-1 — 9 서브패키지 + __init__.py 존재**

```bash
ls best_agent_base/{core,prompts,attachments,tools,hitl,llm,context,api,db}/__init__.py | wc -l
```
Expected: `9`

- [ ] **Step 2: AC-2/AC-3 — 의존성 + uv sync**

```bash
uv tree --depth 1 | grep -E '^(fastapi|uvicorn|sqlalchemy|asyncpg|alembic|pydantic-settings|tiktoken|pytest|pytest-asyncio|ruff|aiosqlite)' | wc -l
uv sync && echo "sync ok"
```
Expected: 카운트 11개 이상, "sync ok"

- [ ] **Step 3: AC-4/AC-5/AC-7/AC-8 — pytest 전체**

```bash
uv run pytest -v
```
Expected: 모든 테스트 (스모크 11 + settings 6 = 17개) PASS, exit 0

- [ ] **Step 4: AC-6 — ruff**

```bash
uv run ruff check .
```
Expected: "All checks passed!", exit 0

- [ ] **Step 5: AC-9 — 인터프리터 import**

```bash
uv run python -c "from best_agent_base import core, prompts, attachments, tools, hitl, llm, context, api, db, config; print('import ok')"
```
Expected: `import ok`

- [ ] **Step 6: AC-10 — .env staged 안 됨**

```bash
echo 'TEST_SECRET=foo' > .env
git status --short | grep -E '^.. \.env$' && echo "FAIL: .env tracked" || echo "ok: .env ignored"
rm .env
```
Expected: `ok: .env ignored`

- [ ] **Step 7: AC-11/12/13 — Docker 검증**

```bash
docker compose ps   # 둘 다 (healthy)
docker exec bab_postgres psql -U postgres -d best_agent_base -c "SELECT 1" | grep -E '^\s*1$' && echo "AC-12 ok"
docker exec bab_redis redis-cli ping | grep -E '^PONG$' && echo "AC-13 ok"
```
Expected: 두 echo 모두 ok.

- [ ] **Step 8: Final commit (Phase 0 완료 마킹)**

```bash
git log --oneline -15
git tag phase-0-skeleton-done
git commit --allow-empty -m "chore: Phase 0 skeleton complete (AC-1..13 all green)"
```

---

## 2. 위험 코드 지점

각 위험은 tech-design.md §6 의 R-N 과 1:1.

- **`pyproject.toml` (Task 1·2 의존성 추가)** — `breaking` (R-1, R-8): langchain 1.x/2.x 와 신규 deps 버전 충돌 가능. **Mitigation**: `uv add` lockfile 결정성 + Task 1 Step 4 의 import smoke 명령 (`uv run python -c "import fastapi, sqlalchemy, ..."`) 로 즉시 검증. langchain 메이저 업그레이드는 본 Phase 범위 외.
- **`pyproject.toml [tool.ruff]` (Task 3)** — `breaking` (R-2): 기존 `main.py`, `best_agent_base/llm/gemini.py` 가 신규 룰셋 위반 가능. **Mitigation**: Task 3 Step 2 의 `ruff check . --fix` 자동 픽스 + 잔여 수동 정리, 룰셋은 `E/F/I` 보수적 선택.
- **`.python-version` + `pyproject.toml` `requires-python` (Task 3)** — `breaking` (R-3): 다른 머신 3.11 → 부팅 실패. **Mitigation**: 변경 없음 — 이미 `.python-version=3.12`, `requires-python=">=3.12"` 박혀 있고 README Task 11 에서 안내. 추가 가드 없음 (디자인 결정).
- **`best_agent_base/config.py` Settings 클래스 (Task 8)** — `side-effect` (R-4): 모듈 레벨 인스턴스화 시 GOOGLE_API_KEY 누락 환경에서 import 자체 깨짐. **Mitigation**: D-12 — 모듈 레벨 `settings = Settings()` 금지. Task 7 의 `test_no_module_level_instance` 테스트가 패턴 자동 강제.
- **9 서브패키지 `__init__.py` (Task 6)** — `perf` (R-5): 모듈 레벨 IO/네트워크 호출 시 smoke 테스트 부팅 느려짐 + 환경 의존성 깨짐. **Mitigation**: D-13 — `__init__.py` 는 한 줄 docstring 만. Task 6 Step 4 의 grep 점검 + Phase 1+ 에도 동일 룰 강제 (TODO.md 룰).
- **`best_agent_base/config.py` `agent_state_dir` (Task 8)** — `side-effect` (R-6): 후속 Phase 가 디렉토리 부재 가정 없이 사용 시 FileNotFoundError. **Mitigation**: Phase 0 OOS 명시. 디렉토리 자동 생성·관리는 Phase 9 첫 사용 시점 (`mkdir(parents=True, exist_ok=True)`) 책임.
- **`best_agent_base/config.py` `database_url` 디폴트 5435 (Task 8)** — `side-effect` (R-7): CI/Postgres 없는 환경에서 연결 시 실패. **Mitigation**: Phase 0 시점은 **연결 안 함** (Settings 만 정의). 단위 테스트는 sqlite 사용 (D-4) — Phase 9 부터.
- **`.env.example` (Task 9)** — `side-effect` (R-9): 실제 시크릿 키 유출 위험. **Mitigation**: Task 9 Step 3 의 grep 패턴 매칭 (`AIza|sk-|key=...`) 으로 의심 패턴 검출.
- **`docker-compose.yml` 호스트 포트 5435 (Task 10)** — `side-effect` (R-10): 또 다른 점유로 부팅 실패 가능. **Mitigation**: `docs/local-dev-setup.md` 의 트러블 섹션에 `lsof -i :5435` 진단 + 포트 변경 절차 명시.
- **`docker-compose.yml` 컨테이너 이름 `bab_postgres`/`bab_redis` (Task 10)** — `side-effect` (R-11): 다른 프로젝트와 이름 충돌. **Mitigation**: `docs/local-dev-setup.md` 트러블 섹션 — 충돌 시 `docker rm bab_postgres` 안내.

---

## 3. 롤백 전략

### Code 롤백
```bash
# 본 Phase 0 작업 전체 되돌리기 — 시작점 (initial bootstrap) 으로 reset
git log --oneline | grep -E '(chore: initial bootstrap)' | head -1   # 해시 확인
git reset --hard <initial-bootstrap-sha>

# 또는 Task 단위 부분 되돌리기
git revert <task-N-commit-sha>

# 또는 가장 마지막 커밋만 안전 되돌리기 (working tree 보존)
git reset --soft HEAD~1
```

### DB 롤백
- Phase 0 은 DB 마이그레이션 없음 — Alembic revision 미생성. **롤백 대상 없음.**
- docker-compose 의 데이터까지 청소: `docker compose down -v`
- Postgres/Redis 컨테이너만 제거(데이터 유지): `docker compose down`

### 설정 롤백
- `.env.example` 변경 되돌리기: `git checkout HEAD~1 -- .env.example`
- `pyproject.toml` 의존성 되돌리기: `git checkout HEAD~N -- pyproject.toml uv.lock && uv sync`
- ruff/pytest 설정 제거: `pyproject.toml` 의 해당 섹션 수동 삭제 후 commit

### 부분 실패 시
- Task K 까지만 진행했다가 K+1 에서 실패 → K 까지의 commit 은 보존, K+1 작업물(unstaged) 만 `git restore .` 또는 `git stash` 로 폐기 후 재시도.

### Worktree 사용 중인 경우
- 본 작업은 `.worktrees/병렬구현-테스트` 또는 `main` 어디서 진행해도 동일 — 워크트리 폐기 시: `git worktree remove .worktrees/병렬구현-테스트 && git branch -D 병렬구현-테스트`

---

## 변경이력
<!-- change-history skill auto-appends entries here, oldest first -->

### [2026-05-03 12:05] [구현계획서-수정]
- **id**: CH-20260503-004
- **이유**: 신규 구현계획서 (Phase 0 — 프로젝트 골격) 최초 작성. requirements + tech-design 을 단계별 TDD task 로 분해 (Task 1~12), 위험 코드 지점·롤백 전략 채움. verify-spec 1차 통과 (gaps 0 / conflicts 0).
- **무엇이**: phase-0-skeleton-implementation-plan.md 전체 (Header + §1 Task 1~12 + §2 R-1~R-11 매핑 + §3 롤백 5 시나리오)
- **영향범위**: phase-0-skeleton-tech-design.md §5 결정·§6 위험·§7 테스트 와 정합. 후속 `/execute-plan` (subagent-driven-development 또는 executing-plans) 의 입력. 본 Phase 의 모든 코드/설정/문서 변경이 본 plan 의 Task 안에서 수행될 예정.
- **연관 항목**: CH-20260503-003 (tech-design 최초 작성), CH-20260503-002 (PRD cascade — Postgres/2-Tier/docker-compose), CH-20260503-001 (PRD 최초 작성)
- **verify 결과**: A. Consistency 31 mapped / 0 gaps / 0 conflicts. C. Impact 13 파일·11 위험 모두 §2 매핑 + mitigation step 구체화. 자동 테스트 17 cases (smoke 11 + settings 6) + Docker 수동 검증 3 ACs.

### [2026-05-03 13:00] [코드-수정]
- **id**: CH-20260503-005
- **이유**: Task 1·2 implementation — base runtime + dev deps via `uv add`. Subagent-driven-development workflow.
- **무엇이**:
  - Task 1 (commit `453e0b7`): 7 base runtime deps 추가 (alembic, asyncpg, fastapi, pydantic-settings, sqlalchemy[asyncio], tiktoken, uvicorn)
  - Task 2 (commit `e83735f`): 4 dev deps 추가 (aiosqlite, pytest, pytest-asyncio, ruff). 본 plan 기재 "expected pytest 8.x" 와 달리 **pytest 9.0.3** 으로 자동 해석됨 (pytest-asyncio 1.3.0 이 pytest 9 명시 지원). 기능 영향 없음, downstream task 진행 시 호환성 재확인 권장.
- **위험 카테고리**: breaking (R-1: 의존성 충돌 가능성 — 둘 다 import smoke + 단위 도구 버전 호출(`pytest --version`, `ruff --version`) 통과로 mitigation 검증)
- **변경 전 코드** (`pyproject.toml`)
  ```toml
  dependencies = [
      "langchain>=1.2.17",
      "langchain-google-genai>=4.2.2",
      "langgraph>=1.1.10",
      "python-dotenv>=1.2.2",
  ]
  ```
- **변경 후 코드** (`pyproject.toml`)
  ```toml
  dependencies = [
      "alembic>=1.18.4",
      "asyncpg>=0.31.0",
      "fastapi>=0.136.1",
      "langchain>=1.2.17",
      "langchain-google-genai>=4.2.2",
      "langgraph>=1.1.10",
      "pydantic-settings>=2.14.0",
      "python-dotenv>=1.2.2",
      "sqlalchemy[asyncio]>=2.0.49",
      "tiktoken>=0.12.0",
      "uvicorn>=0.46.0",
  ]

  [dependency-groups]
  dev = [
      "aiosqlite>=0.22.1",
      "pytest>=9.0.3",
      "pytest-asyncio>=1.3.0",
      "ruff>=0.15.12",
  ]
  ```
- **영향범위**: `pyproject.toml` + `uv.lock` 만. 다른 파일 무. spec/quality 양쪽 review 통과.
- **연관 항목**: CH-20260503-004 (plan 최초 작성)

### [2026-05-03 15:30] [코드-수정]
- **id**: CH-20260503-006
- **이유**: Task 3 ~ Task 12 + 부수 fix 3개 implementation 완료. Phase 0 전체 GREEN. Subagent-driven-development workflow.
- **무엇이** (commit 별):
  - **Task 3** (`5c967c6`): `pyproject.toml [tool.ruff]` + `[tool.ruff.lint]` (line-length=100, py312, E/F/I)
  - **Task 4** (`a20e0ae`): `pyproject.toml [tool.pytest.ini_options]` (testpaths=tests, asyncio_mode=auto)
  - **Task 5** (`329ef8a`): `tests/__init__.py` + `tests/test_smoke.py` (RED — 10 failed / 1 passed)
  - **Task 6** (`a51931c`): 9 신규 파일 — 8 서브패키지 `__init__.py` + `best_agent_base/config.py` placeholder. Smoke GREEN (11 passed)
  - **Task 6.5 fix** (`b1a8e86`): D-13 violation 정렬 — `best_agent_base/__init__.py`/`llm/__init__.py` 의 편의 import 제거 (docstring-only), `main.py` import 경로 갱신 (`best_agent_base.llm.gemini` 직접 사용). T6 코드 리뷰어가 발견.
  - **Task 7** (`bdc3faa`): `tests/test_settings.py` 6 cases (RED — Settings 미정의)
  - **Task 7 fix** (`685ceee`): T4 의 lazy 룰 검증을 hardcoded name list → `isinstance(v, mod.Settings)` scan 으로 일반화. T7 코드 리뷰어 Important 사항.
  - **Task 8** (`93f1ece`): `best_agent_base/config.py` 본체 — `Settings(BaseSettings)` 6 필드 (google_api_key 필수, log_level/database_url/agent_state_dir 디폴트, redis_url/blob_store_url Optional). GREEN (17/17 통과)
  - **T8 follow-up style fix** (`7233e6c`): `tests/test_settings.py:26` E501 (line >100) — env 키 튜플 multi-line 분리.
  - **Task 9** (`db40895`): `.env.example` 갱신 (호스트 5435, REDIS/BLOB Optional placeholder, Korean comments)
  - **Task 10** (`5e243a4`): `docker-compose.yml` 생성 — postgres:16-alpine (5435:5432) + redis:7-alpine (6379:6379), healthchecks, named volumes. **Live 검증**: 둘 다 `Up (healthy)`, `SELECT 1` ok, `PING → PONG` ok.
  - **Task 11** (`68c91a9`): `README.md` Setup 섹션 4 단계 (uv sync / .env / docker compose / verification) + 5435 포트 노트 + `docs/local-dev-setup.md` 링크.
  - **Task 12** (`5a844ae` 빈 마커): AC-1 ~ AC-13 전수 검증 13/13 GREEN.
- **위험 카테고리**: 다중 (R-1, R-2, R-4, R-5, R-7~R-11) — 각 task 의 spec/quality 리뷰 + AC 자동 검증으로 mitigation 검증 완료.
- **영향범위**: 13 파일 (신규 11 + 수정 4 — `pyproject.toml` 4회, `.env.example` 1회, `README.md` 1회, `main.py` 1회 [import 한 줄], `best_agent_base/__init__.py` 1회 [docstring 화]). `tests/test_smoke.py` 11 cases + `tests/test_settings.py` 6 cases = 17 cases 자동 회귀 가드. ruff/pytest 모든 단계 exit 0. Docker 인프라 live 동작.
- **Phase 0 → Phase 1+ 인계**:
  - 9 서브패키지 골격 + 4 워크플로우 인프라 (docker, env, lint, test) 즉시 사용 가능.
  - `Settings` 진입점으로 모든 후속 Phase 의 환경 통합.
  - 2-Tier 저장 모델 슬롯 (Settings 의 `redis_url`/`blob_store_url` Optional) 준비됨, 본체는 Phase 9.
- **Final code review (전체)**: APPROVED-TO-MERGE. 6 개 Phase 1+ grooming 노트:
  1. README status 라벨 갱신 ("Phase 0 진입 직전" → "Phase 0 완료")
  2. `main.py` 의 `load_dotenv()` 직접 호출 → `Settings()` 진입점 사용으로 마이그레이션 (FR-3 단일 진입점 원칙 강화)
  3. `tests/conftest.py` 도입 (Phase 1 부터 공통 async fixture 필요 시)
  4. docker container 이름 (`bab_*`) 충돌 정책 재고 (현재 R-11 로 acceptance)
  5. `Settings.log_level` 을 `Literal[...]` 로 강화
  6. `Settings.agent_state_dir` 을 `Path` 로 정규화 (Phase 9 캐시/블롭 본체에서)
- **연관 항목**: CH-20260503-005 (T1·T2), CH-20260503-004 (plan 최초), CH-20260503-003 (tech-design), CH-20260503-002 (PRD cascade), CH-20260503-001 (PRD 최초)
- **태그**: `phase-0-skeleton-done` → commit `68c91a9` (T11 README), 마커 `5a844ae` (Phase 0 complete empty commit)
