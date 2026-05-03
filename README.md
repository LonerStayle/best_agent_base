# best_agent_base

> **모든 에이전트 프로젝트의 베이스가 되는 파이썬 백엔드 모듈.**

다른 프로젝트가 `import best_agent_base` 한 번으로 시작할 수 있는 **인터페이스·계약 중심의 골격**을 제공한다. 핵심 기법 — 시스템 프롬프트 정적/동적 분리, 프롬프트 캐싱, 어태치먼트, 도구 검증·서치, ReAct 흐름, HITL, 컨텍스트 관리, 도구 실행 파이프라인 — 을 베이스화한다.

전체 로드맵은 [`TODO.md`](./TODO.md) 참조.

---

## Stack

- **Python 3.12+**
- **uv** — 패키지/가상환경 관리
- **LangGraph** — ReAct 루프 프레임
- **LLM**: Google Gemini (`langchain-google-genai`) — 기본 모델 `gemini-3-flash`
- **API**: FastAPI + SQLAlchemy (후반 Phase)

---

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

---

## Project Layout (목표)

```
best_agent_base/
├── core/          # 하네스 · 세션 · ReAct 루프
├── prompts/       # 시스템 프롬프트 정적/동적 분리
├── attachments/   # 이중 어태치먼트 시스템
├── tools/         # 도구 베이스 + 빌트인 + ToolSearch
├── hitl/          # human-in-the-loop (권한 + 비동기 대기)
├── llm/           # 모델 래퍼 (현재 Gemini)
├── context/       # 컨텍스트 관리 (컴팩션, 핸드오프, FS 응용)
├── api/           # FastAPI 엔드포인트
└── db/            # SQLAlchemy 모델
```

> Phase 0에서 위 골격을 빈 껍데기로 만들고, 이후 Phase에서 한 폴더씩 채운다.

---

## Workflow — `js-super` only

모든 작업은 `js-super` 플러그인의 표준 파이프라인으로 진행한다.

```
/brainstorm → /design → /write-plan → /execute-plan → /api-test* → finishing-a-development-branch
```

- **Phase 1개 = `js-super` 풀 사이클 1회** (중간 단계 임의 생략 금지)
- `/api-test`만 조건부 스킵 허용 (API 노출 없는 Phase, 인터페이스/추상만 다루는 Phase 등)

상세는 [`TODO.md` → 진행 방식 합의](./TODO.md) 참조.

---

## Status

🟡 **Phase 0 (프로젝트 골격) 진입 직전.**

진척 상황은 [`TODO.md`](./TODO.md)의 체크박스로 추적.
