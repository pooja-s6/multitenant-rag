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

## Not implemented yet

These routes exist and return `501`:

- `GET` and `POST /api/documents`
- `POST /api/rag/query`
- `GET /api/dashboard/summary`
