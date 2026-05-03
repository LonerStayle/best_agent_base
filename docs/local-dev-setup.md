# Local Dev Setup — Postgres + Redis

`best_agent_base` 의 로컬 개발 환경. Docker Compose 로 Postgres(host port **5435**) 와 Redis(6379) 를 한 번에 부팅한다.

> **포트 5435 메모**: 호스트의 5432 가 다른 프로젝트(기존 Postgres)에 점유돼 있어 충돌 회피 차원에서 **5435** 사용. 컨테이너 내부 포트는 5432 그대로.

---

## 1. 사전 준비

- Docker Desktop (Mac/Win) 또는 Docker Engine + Compose v2
- 호스트 포트 **5435**, **6379** 가 비어 있어야 함

```bash
# 점유 확인
lsof -i :5435
lsof -i :6379
```

---

## 2. `docker-compose.yml` (프로젝트 루트)

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
      - "5435:5432"   # host:container
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

---

## 3. 명령 모음

```bash
# 시작 (백그라운드)
docker compose up -d

# 상태 확인
docker compose ps

# 로그 보기
docker compose logs -f postgres
docker compose logs -f redis

# 재시작
docker compose restart

# 정지 (데이터 유지, 컨테이너 정지만)
docker compose stop

# 정지 + 컨테이너 제거 (데이터는 볼륨에 유지)
docker compose down

# 데이터까지 깔끔히 제거 (재현/초기화)
docker compose down -v
```

---

## 4. 접속 검증

### Postgres

```bash
# 호스트에서 (호스트 포트 5435)
psql postgresql://postgres:postgres@localhost:5435/best_agent_base -c "SELECT version();"

# 컨테이너 내부에서
docker exec -it bab_postgres psql -U postgres -d best_agent_base -c "SELECT version();"
```

### Redis

```bash
# 호스트에서
redis-cli -p 6379 ping
# → PONG

# 컨테이너 내부에서
docker exec -it bab_redis redis-cli ping
# → PONG
```

---

## 5. `.env` 설정

`.env.example` 을 복사한 뒤 키 채움:

```bash
cp .env.example .env
```

`.env` 핵심 항목:

```bash
GOOGLE_API_KEY=<your-key>

# Postgres — 위 docker-compose 와 정렬
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5435/best_agent_base

# Redis — 비워두면 EphemeralCache 가 FS 백엔드로 fallback,
# 채우면 자동으로 Redis 백엔드로 전환
REDIS_URL=redis://localhost:6379/0

# Object storage — 비우면 BlobStore 가 FS 백엔드 (디폴트)
# 프로덕션에선 s3://... 등으로 교체
# BLOB_STORE_URL=

LOG_LEVEL=INFO
AGENT_STATE_DIR=./.agent_state
```

---

## 6. 자주 만나는 트러블

| 증상 | 원인 | 해결 |
|---|---|---|
| `bind: address already in use` (5435) | 다른 컨테이너가 5435 점유 | `lsof -i :5435` 로 잡고 정지 또는 docker-compose 의 호스트 포트 변경 |
| `connection refused` from app | Postgres 부팅 중 (healthcheck 미완료) | `docker compose ps` 에서 `(healthy)` 확인 후 재시도 |
| 데이터가 사라짐 | `docker compose down -v` 실행됨 | `-v` 는 볼륨 제거 — 의도적이 아니면 사용 금지 |
| 컨테이너 이름 충돌 | 다른 프로젝트에서 같은 이름 사용 | `container_name` 변경 또는 충돌 컨테이너 정리 (`docker rm bab_postgres`) |
| Redis 키 사라짐 (재시작 후) | 디폴트는 RDB만, 짧은 주기는 휘발 가능 | EphemeralCache 시맨틱상 정상 — 사라져도 시스템 정상 동작이 원칙 |

---

## 7. 데이터 청소 (개발 중 잦음)

```bash
# Postgres 만 데이터 reset (테이블 drop & recreate)
docker compose down -v postgres && docker compose up -d postgres

# 전체 reset
docker compose down -v && docker compose up -d
```

---

## 8. 멀티 인스턴스·프로덕션 메모

- 본 docker-compose 는 **로컬 dev 전용**. 프로덕션은 RDS/Cloud SQL + ElastiCache/Memorystore 등 매니지드 서비스로.
- 프로덕션에선 `.env` 의 `DATABASE_URL` / `REDIS_URL` / `BLOB_STORE_URL` 만 교체하면 됨 — 코드 변경 무 (원칙 #8 교체 가능성).
