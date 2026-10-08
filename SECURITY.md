# Security

Authorization uses the database user row after the JWT is verified. The tenant id in the token must match that row. Role checks read the role stored in the database, not a role that was only present when the token was issued.

## Invariants covered by the test suite

- A token from one tenant cannot read or change another tenant.
- A user cannot retrieve another tenant's chunks, even when that chunk is the nearest vector.
- A user outside `allowed_roles` cannot retrieve a private document.
- Private text and another tenant's text stay out of the RAG answer.
- A cached answer is reused only for the same tenant and the same permission context.
- Dashboard totals include only the caller's tenant.
- Logs omit secrets and database URLs.
- Production startup rejects the placeholder `JWT_SECRET`.

Run the suite from `backend/` with Compose Postgres available:

```bash
pytest
```

Passwords are hashed with bcrypt. `.env` is gitignored. `.env.example` contains placeholders only.
