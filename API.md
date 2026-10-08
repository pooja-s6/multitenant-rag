# API

Base URL: `http://localhost:8000`

Protected routes expect `Authorization: Bearer <access_token>`. The token's tenant must match the user row. Role checks use the role stored for that user.

Error bodies look like `{"detail": "..."}`.

## Health

`GET /api/health/live` returns `200` and `{"status": "ok"}`.

`GET /api/health/ready` returns `200` when Postgres and Redis accept a check. Otherwise it returns `503` and `status: "degraded"` with a `checks` object. Dependency failures are reported as `unavailable` and do not include connection strings.

## Authentication

`POST /api/auth/login`

```json
{"email": "admin@acme.example", "password": "correct-horse-1"}
```

`200` response:

```json
{"access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600}
```

Unknown email and wrong password both return `401` with `Invalid credentials`.

`GET /api/auth/me` returns the caller:

```json
{
  "user_id": "uuid",
  "tenant_id": "uuid",
  "role": "ADMIN",
  "email": "admin@acme.example",
  "department": null
}
```

Missing, expired, tampered, or cross-tenant tokens return `401`.

## Tenants

`POST /api/tenants` creates a tenant and its first `ADMIN` user.

```json
{
  "name": "Acme",
  "slug": "acme",
  "admin_email": "admin@acme.example",
  "admin_password": "correct-horse-1",
  "admin_department": "engineering"
}
```

While the user table is empty, this call does not require a token. After that, only an `ADMIN` may create another tenant. The caller does not become a member of the new tenant. `USER` and `MANAGER` receive `403`. Duplicate slug or email returns `409`.

`GET /api/tenants` returns a one-item list: the caller's tenant.

`GET /api/tenants/{tenant_id}` returns that tenant when the id is the caller's tenant. Any other id returns `404`.

`PATCH /api/tenants/{tenant_id}` updates the name. `ADMIN` only, and only for the caller's tenant.

`DELETE /api/tenants/{tenant_id}` deletes the caller's tenant and its users. `ADMIN` only. Another tenant's id returns `404`.

## Users

`GET /api/users` lists users in the caller's tenant. `ADMIN` and `MANAGER` may call it. `USER` receives `403`.

`POST /api/users` creates a user in the caller's tenant. `ADMIN` only. The body has `email`, `password`, `role` (`ADMIN`, `MANAGER`, or `USER`), and optional `department`. There is no tenant field; the tenant comes from the token.

Passwords are stored as bcrypt hashes and are not returned.

## Documents

Every document route requires `Authorization: Bearer <access_token>`. The tenant is the token's tenant. A `tenant_id` sent with the upload is ignored.

`POST /api/documents` accepts one multipart field named `file`, plus optional `access_level` (`public`, `internal`, or `private`), `department`, and `allowed_roles` (comma-separated roles, used when the level is `private`). The default level is `internal`, which `MANAGER` and `ADMIN` can retrieve. Allowed types are PDF (`.pdf`), UTF-8 text (`.txt`), and Markdown (`.md`, `.markdown`). The response is `201` with the document id, filename, content type, size, chunk count, stored permission, and the stored chunks (index, page number, and text). Embeddings are not returned.

Empty files, files with no extractable text, and unsupported types return `400`. Files larger than `MAX_UPLOAD_SIZE_MB` return `413`. A failed embedding does not leave a document or chunk row.

`GET /api/documents` lists the caller's tenant only.

`GET /api/documents/{document_id}` returns one document and its chunks. Another tenant's id returns `404`.

`DELETE /api/documents/{document_id}` returns `204` for the caller's document and `404` for any other id.

These routes do not call a language model.

## Retrieval

`POST /api/retrieval/search` requires a bearer token. The body has `query` and may include `top_k`, `similarity_threshold`, `department`, and `access_level`.

The tenant comes from the token. Results are chunks from that tenant that the caller's role and department are allowed to read, ordered by cosine similarity. Rows below `RETRIEVAL_SIMILARITY_THRESHOLD` are omitted. `top_k` cannot exceed `RETRIEVAL_TOP_K`, and `similarity_threshold` cannot go below the configured threshold. `department` and `access_level`, when sent, only remove additional rows.

`ADMIN` can read every document in the tenant, including other departments. `public` documents are readable by every authenticated user in the tenant. `internal` documents are readable by `MANAGER` and `ADMIN`. `private` documents are readable by the listed roles, and by `ADMIN`. A department on the document must match the caller unless the caller is an `ADMIN`.

The response is `{ "chunks": [ ... ] }`. Each chunk has `chunk_id`, `document_id`, `filename`, `content`, `page_number`, `access_level`, `department`, and `score`. Embeddings are not returned. An empty list means nothing allowed was similar enough. Another tenant's chunks are never included.

## Questions

`POST /api/rag/query` requires a bearer token. The body has `query` and may include the same narrowing fields as search: `top_k`, `similarity_threshold`, `department`, and `access_level`.

The handler retrieves allowed chunks, ranks them by similarity, and asks the language-model provider. A cache miss scores the question from its length, sentence count, question type, retrieval confidence, chunk count, and ambiguity. A score above `ROUTING_COMPLEXITY_THRESHOLD` uses `LARGE_MODEL` and the large-model prices. A lower score uses `SMALL_MODEL` and the small-model prices. `LLM_PROVIDER=openai` with `LLM_API_KEY` set calls `LLM_BASE_URL` with the chosen model. An empty key uses the local fake provider, which answers from the retrieved excerpt. The response has:

- `answer`
- `sources` (document id, chunk id, filename, page number, score, excerpt)
- `model_used`
- `cache_hit` (`true` only when a cached answer is reused)
- `latency` (milliseconds)
- `request_id`

A completed query is stored in `query_logs` for that tenant, including token counts, the estimated cost of the model that ran, and `cost_saved` when a later hit reuses that answer. Private documents and other tenants' documents are not retrieved, so they do not appear in the answer or the sources.

Before calling the model, the handler looks for a cached answer. A hit requires the same tenant, the same role and department, the same `department` and `access_level` filters, a cosine similarity of at least `CACHE_SIMILARITY_THRESHOLD`, and an entry that has not passed `CACHE_TTL`. The stored citations are returned and the model is not called. Another tenant, another role, or a different filter is a miss. Answers with no sources are not cached. If Redis cannot be reached, the request is a miss and the query still completes.

## Dashboard

`GET /api/dashboard/summary` requires a bearer token. Every count is limited to the caller's tenant. The body includes total queries, cache hits, cache misses, hit rate, average latency, P95 latency, input tokens, output tokens, estimated cost, estimated cost saved, and model distribution. Those figures are summed from `query_logs`. An `ADMIN` also receives `queries_by_tenant` for that same tenant. A non-admin receives `queries_by_tenant: null`. Another tenant's rows are never included.
