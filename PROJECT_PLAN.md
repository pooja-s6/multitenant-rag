# Project plan

Implementation follows the architecture in `ARCHITECTURE.md`. Each phase ends with its tests passing before the next phase starts.

## Current status

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Structure, configuration, Docker, health skeleton | Complete |
| 2 | Database, authentication, tenants | Complete |
| 3 | Document ingestion and embeddings | Complete |
| 4 | Vector retrieval and permission filtering | Complete |
| 5 | RAG pipeline | Complete |
| 6 | Semantic caching | Complete |
| 7 | Cost-aware model routing | Complete |
| 8 | Observability and analytics | Complete |
| 9 | React dashboard and chat UI | Complete |
| 10 | Evaluation, security tests, Docker validation, docs | Complete |

## Working agreements

- Tenant id and role used for authorization come from the JWT.
- A failing test is fixed before the next phase begins.
- Secrets stay in the environment. `.env` is never committed.
- LLM calls go through a provider interface. Tests use a fake provider.
- New behavior ships with pytest coverage for the security invariants it touches.

## Phase 1 — Structure and infrastructure

Deliver:

- `ARCHITECTURE.md`, `PROJECT_PLAN.md`, and a README that describes how to run the skeleton
- backend package layout, settings, logging, Alembic environment, health API
- placeholder routers so the URL map is stable
- React + TypeScript + Vite + Tailwind shell with four routes
- `docker-compose.yml`, Dockerfiles, `.env.example`, Postgres init for `vector`

Exit criteria:

- `pytest` passes in `backend/`
- `npm run build` passes in `frontend/`
- `docker compose config` succeeds
- `GET /api/health/live` returns 200 from the backend container after `docker compose up --build`

Out of scope: user tables, login, uploads, embeddings, retrieval, RAG, cache, routing, dashboard metrics, evaluation results.

## Phase 2 — Database, authentication, tenants

Deliver:

- SQLAlchemy models and the initial Alembic migration for `tenants` and `users`
- bcrypt password hashing and JWT issue/verify
- `POST /api/auth/login` and `GET /api/auth/me`
- tenant creation restricted to `ADMIN`
- dependency that yields `user_id`, `tenant_id`, and `role`
- tests for login, password rejection, and role checks

Delivered: `tenants` and `users` tables, Alembic revision `0001_tenants_users`, bcrypt hashes, JWT login and `/api/auth/me`, tenant CRUD scoped to the caller's tenant, and user create/list. The first tenant can be created only while the user table is empty. After that, only an `ADMIN` can create tenants or users. A token is accepted only when its `tenant_id` matches the user row, and the role is read from the database.

Exit criteria: an authenticated request resolves the three identity fields, and a token from tenant A cannot be treated as tenant B.

## Phase 3 — Ingestion and embeddings

Deliver:

- PDF, TXT, and Markdown extraction, cleaning, and chunking
- sentence-transformers embeddings behind a small embedder interface
- document and chunk persistence
- upload API for any authenticated user in the tenant
- tests with fixture files and a fake embedder so the suite does not download models

Delivered: `documents` and `document_chunks` tables, Alembic revision `0002_documents_chunks`, and `POST`, `GET`, and `DELETE /api/documents`. The tenant comes from the JWT. Chunks store `tenant_id`, `document_id`, filename metadata, a page number for PDFs, and a 384-dimension vector. Fictional sample files live in `data/sample_documents/` and are uploaded through the same API as any other file. Document permissions and access metadata are Phase 4.

Exit criteria: a stored chunk carries tenant id, document id, filename, and page when available. Access metadata arrives with permission-aware retrieval.

## Phase 4 — Retrieval and permissions

Deliver:

- pgvector similarity search
- SQL filters for tenant, access level, allowed roles, and department
- configurable `top_k` and similarity threshold
- tests that tenant B rows and unauthorized private rows are absent even when their vectors are nearest

Delivered: `document_permissions` plus access columns on `document_chunks`, Alembic revision `0003_document_permissions`, and `POST /api/retrieval/search`. Upload accepts `access_level`, `department`, and `allowed_roles`. The default access level is `internal`. Search embeds the query, then applies tenant, role, department, `top_k`, and the similarity threshold in one query. A request can raise the threshold or lower `top_k`. It cannot widen either. Tests cover a nearer private chunk and a nearer other-tenant chunk, both of which stay out of the result.

Exit criteria: the retrieval service returns only chunks the caller is allowed to read.

## Phase 5 — RAG pipeline

Deliver:

- preprocessing, retrieval, ranking, prompt construction, provider call, citations
- fake LLM provider plus an OpenAI-compatible provider selected by `LLM_PROVIDER`
- `POST /api/rag/query` response contract from the architecture
- query log write for each request

Delivered: `POST /api/rag/query` and Alembic revision `0004_query_logs`. The handler preprocesses the question, retrieves only chunks the caller may read, ranks them by similarity, builds a prompt, and calls a provider. `LLM_PROVIDER=openai` with an API key uses the OpenAI-compatible chat endpoint and `SMALL_MODEL`. An empty key, or `LLM_PROVIDER=fake`, uses a local provider that answers from the retrieved text. Every completed query is stored in `query_logs` with model, token counts, estimated small-model cost, latency, and sources. `cache_hit` is false. Semantic cache and complexity routing are later phases.

Exit criteria: the endpoint returns an answer, sources, model, cache flag, latency, and request id. With an empty cache, `cache_hit` is false.

## Phase 6 — Semantic cache

Deliver:

- Redis entry format and cosine lookup described in the architecture
- tenant prefix and permission-context hash on every read and write
- hit, miss, cost-saved, and latency-saved counters
- tests for hit, miss, cross-tenant rejection, and cross-permission rejection

Delivered: a Redis semantic cache in front of the RAG provider. The query is embedded once. Lookup scans only keys for that tenant and a hash of the caller's role, department, and the request's access-level and department filters. The best entry is reused when cosine similarity is at least `CACHE_SIMILARITY_THRESHOLD`, the entry is unexpired, and the stored tenant and permission context match. A hit skips the model, returns the stored citations, and logs `cache_hit` true with zero token cost. Hits, misses, estimated cost saved, and latency saved are counted per tenant. A miss still calls the provider. Answers with no sources are not stored, so a later upload can still be found. If Redis is unreachable the query proceeds as a miss. Each tenant and permission context keeps at most 50 entries.

Exit criteria: a cached answer is reused only for the same tenant and permission context.

## Phase 7 — Routing and cost

Deliver:

- complexity score and threshold from settings
- pricing table from environment variables
- per-request token and cost record
- tests for small-model routing, large-model routing, and cost arithmetic

Delivered: `ModelRouter` scores length, sentence count, question type, retrieval confidence, chunk count, and ambiguity. A score above `ROUTING_COMPLEXITY_THRESHOLD` selects `LARGE_MODEL` and the large-model prices. Otherwise the small model and its prices are used. Estimated cost is `(input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)`. Tests cover a short question, a compare/why question, and a price change.

Exit criteria: simple and complex queries select different models, and cost changes when prices change without code edits.

## Phase 8 — Observability and analytics

Deliver:

- JSON logs for RAG requests with the required fields
- dashboard service for the metrics listed in the architecture
- `GET /api/dashboard/summary` scoped so a non-admin sees their tenant, and an admin can see tenant breakdown for their own tenant unless a later product rule adds a platform admin

Delivered: RAG request logs are JSON and include `request_id`, `tenant_id`, `user_id`, latency, model, `cache_hit`, retrieved chunk count, and estimated cost. `GET /api/dashboard/summary` sums `query_logs` for the caller's tenant: totals, hit rate, average latency, P95, tokens, cost, cost saved, and model distribution. An admin also receives `queries_by_tenant` for that tenant. Alembic revision `0005_query_log_cost_saved` stores the avoided cost on a hit.

Exit criteria: metrics match rows in `query_logs` for a fixture set, including cache hit rate, average latency, and P95.

## Phase 9 — Dashboard and chat UI

Deliver:

- working login, upload, chat, and dashboard pages against the API
- chat shows citations, cache hit, and model used
- dashboard shows the Phase 8 metrics and recent queries

Delivered: the login page stores the bearer token in `sessionStorage`. Documents can be uploaded, listed, and deleted. Chat shows the answer, citations, cache flag, model, and latency. The dashboard shows the Phase 8 metrics. Routes other than login require a token.

Exit criteria: a user can log in, upload an allowed file, ask a question, and see the RAG response fields in the browser.

## Phase 10 — Evaluation, hardening, documentation

Deliver:

- evaluation set of realistic questions
- comparison of plain RAG, RAG plus cache, RAG plus routing, and RAG plus both
- `API.md`, `SECURITY.md`, `EVALUATION.md`, and a README that includes measured results from that run
- Docker Compose smoke test of health, login, and a RAG call with the fake provider
- the security tests listed in the product requirements, kept green

Delivered: `data/evaluation/questions.json`, `EVALUATION.md`, and `SECURITY.md`. The four-way comparison in `tests/test_evaluation.py` checks plain RAG, cache, routing, and both on the fake provider. Security tests for tenant isolation, private documents, cache permission context, and dashboard scope stay in the suite.

Exit criteria: documentation matches the running system, and the security tests pass.

## Risks

| Risk | Mitigation |
| --- | --- |
| Embedding model download makes tests slow and brittle | Fake embedder in unit tests; real model only in an optional integration path |
| pgvector filter + index returns unauthorized neighbors | Tenant and permission predicates are in the SQL, with tests that would fail if they were dropped |
| Semantic cache leaks across tenants | Key prefix plus an explicit tenant check before a hit is returned |
| Local Python is newer than the Docker image | Application code targets 3.11. Docker uses 3.11. Tests also run on the developer interpreter |
| Provider cost math drifts | Prices stay in configuration and have direct unit tests |
