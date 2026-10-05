# Multi-Tenant RAG Platform

A platform for document question-answering where each tenant's documents, chunks, and cached answers stay inside that tenant. Within a tenant, document permissions decide which roles can retrieve a chunk. Repeated questions can be served from a semantic cache, and simpler questions can be routed to a smaller model so cost stays visible.

The design contract is [ARCHITECTURE.md](ARCHITECTURE.md). The build order is [PROJECT_PLAN.md](PROJECT_PLAN.md).

## Current status

Phase 2 is in place: project layout, Docker Compose, health checks, tenants, users, and JWT authentication. Document ingestion, retrieval, RAG, caching, routing, and dashboard metrics are specified and not built yet. Those routes respond with HTTP 501 until their phase lands.

## Architecture

```text
Browser (React) → FastAPI → PostgreSQL/pgvector
                         → Redis
                         → configurable LLM provider
```

Every authenticated call resolves `user_id`, `tenant_id`, and `role` from a JWT and the user row. Retrieval and cache reads in later phases will filter on that tenant before returning anything. See the architecture doc for the permission rules, cache safety checks, and routing score.

## Features

| Area | Phase 1 | Planned |
| --- | --- | --- |
| Health checks | Live and ready endpoints | — |
| Auth and tenants | JWT login, bcrypt passwords, tenant CRUD, roles | Document permissions at retrieval time |
| Documents | Routes reserved | PDF, TXT, Markdown ingestion |
| RAG chat | Page shell | Answers, citations, model, cache flag |
| Semantic cache | — | Redis similarity lookup scoped by tenant and permissions |
| Model routing | Settings only | Small model for simple queries, large model for complex ones |
| Dashboard | Shows Postgres and Redis health | Query, latency, and cost metrics |

## Setup

Requirements: Docker with Compose, or Python 3.11+ and Node 22 for local processes. The backend image uses Python 3.11.

```bash
cp .env.example .env
```

Change `JWT_SECRET` before any shared deployment. Leave `LLM_API_KEY` empty to keep the fake provider once it exists. Do not commit `.env`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL for PostgreSQL |
| `REDIS_URL` | Redis connection URL |
| `JWT_SECRET` | Signing key for access tokens |
| `EMBEDDING_MODEL` | Sentence-transformers model name |
| `LLM_PROVIDER` | Provider id (`openai` or the later fake provider) |
| `SMALL_MODEL` / `LARGE_MODEL` | Routed model names |
| `CACHE_SIMILARITY_THRESHOLD` | Minimum cosine similarity for a cache hit |
| `CACHE_TTL` | Cache entry lifetime in seconds |
| `RETRIEVAL_TOP_K` | Maximum chunks returned |
| `SMALL_MODEL_PRICE` / `LARGE_MODEL_PRICE` | USD per 1,000,000 input tokens |
| `SMALL_MODEL_OUTPUT_PRICE` / `LARGE_MODEL_OUTPUT_PRICE` | USD per 1,000,000 output tokens |

`.env.example` lists every variable, including CORS, embedding dimension, and the routing threshold.

Compose sets `DATABASE_URL` and `REDIS_URL` to the `postgres` and `redis` service names. The example file uses `localhost` for processes you run yourself.

## Running locally

All services:

```bash
docker compose up --build
```

- App: http://localhost:8080
- API: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/health/live

Backend only, from `backend/`:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

On macOS or Linux, activate `.venv/bin/activate` instead.

Frontend only, from `frontend/`:

```bash
npm install
npm run dev
```

Vite serves http://localhost:5173 and proxies `/api` to http://localhost:8000.

Postgres in Compose creates the `vector` extension the first time the data volume is initialized.

Apply database migrations from `backend/` after Postgres is up:

```bash
alembic upgrade head
```

## API usage

Request and response details are in [API.md](API.md).

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/api/health/live` | `200` and `{"status":"ok"}` |
| `GET` | `/api/health/ready` | `200` when Postgres and Redis respond, otherwise `503` |
| `POST` | `/api/auth/login` | Email and password. Returns a bearer token |
| `GET` | `/api/auth/me` | Current `user_id`, `tenant_id`, and `role` |
| `POST` | `/api/tenants` | Creates a tenant and its first admin |
| `GET` | `/api/tenants` | Returns only the caller's tenant |
| `GET`, `PATCH`, `DELETE` | `/api/tenants/{tenant_id}` | Own tenant only. Other tenants respond as not found |
| `GET`, `POST` | `/api/users` | Users in the caller's tenant |
| `GET`, `POST` | `/api/documents` | `501` |
| `POST` | `/api/rag/query` | `501` |
| `GET` | `/api/dashboard/summary` | `501` |

Interactive docs: http://localhost:8000/docs

The first `POST /api/tenants` is open only while no users exist, so the deployment can create its first admin. After that, creating a tenant or a user requires an `ADMIN` token. Send `Authorization: Bearer <access_token>` on protected routes.

## Testing

From `backend/`:

```bash
pytest
```

The suite expects the Compose Postgres at `localhost:5432` (user `rag`, password `rag`). It creates a `rag_test` database and runs migrations there. Set `TEST_DATABASE_URL` if that server is elsewhere. On this workstation, run pytest inside Ubuntu WSL so it reaches the Compose database rather than another Postgres on the Windows host.

Auth tests cover login, invalid credentials, expired and tampered tokens, protected routes, role checks, and tenant isolation. Permission filters, cache boundaries, routing, and cost tests arrive with those phases.

Frontend production bundle:

```bash
cd frontend
npm run build
```

## Evaluation

An evaluation set and the four-way comparison (plain RAG, cache, routing, cache plus routing) are Phase 10. This repository does not report quality, hit rate, latency, or cost numbers yet.

## Limitations

- The React login page does not store the token yet. Sign-in works through the API.
- Uploads, retrieval, and questions are not functional.
- Embeddings and LLM calls are not installed in the image.
- Readiness depends on the configured Postgres and Redis endpoints.

## Further work

Phases 3 through 10 in `PROJECT_PLAN.md`: ingestion, permission-aware retrieval, the RAG pipeline, semantic caching, cost-aware routing, metrics, the interactive UI, and evaluation.
