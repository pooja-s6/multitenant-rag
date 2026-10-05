from fastapi.testclient import TestClient

PASSWORD = "correct-horse-1"


def _body(slug: str, email: str, name: str = "Acme") -> dict[str, str]:
    return {
        "name": name,
        "slug": slug,
        "admin_email": email,
        "admin_password": PASSWORD,
    }


def _login(client: TestClient, email: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_first_tenant_can_be_created_without_a_token(client: TestClient) -> None:
    response = client.post("/api/tenants", json=_body("acme", "admin@acme.example"))
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "acme"
    assert "password" not in body


def test_later_tenant_creation_requires_an_admin(client: TestClient) -> None:
    client.post("/api/tenants", json=_body("acme", "admin@acme.example"))
    anonymous = client.post("/api/tenants", json=_body("beta", "admin@beta.example"))
    assert anonymous.status_code == 401

    admin_token = _login(client, "admin@acme.example")
    created_user = client.post(
        "/api/users",
        json={"email": "user@acme.example", "password": PASSWORD, "role": "USER"},
        headers=_auth(admin_token),
    )
    assert created_user.status_code == 201
    user_token = _login(client, "user@acme.example")
    as_user = client.post(
        "/api/tenants",
        json=_body("beta", "admin@beta.example"),
        headers=_auth(user_token),
    )
    assert as_user.status_code == 403

    created_manager = client.post(
        "/api/users",
        json={"email": "manager@acme.example", "password": PASSWORD, "role": "MANAGER"},
        headers=_auth(admin_token),
    )
    assert created_manager.status_code == 201
    manager_token = _login(client, "manager@acme.example")
    as_manager = client.post(
        "/api/tenants",
        json=_body("beta", "admin@beta.example"),
        headers=_auth(manager_token),
    )
    assert as_manager.status_code == 403

    as_admin = client.post(
        "/api/tenants",
        json=_body("beta", "admin@beta.example", name="Beta"),
        headers=_auth(admin_token),
    )
    assert as_admin.status_code == 201


def test_token_from_tenant_a_cannot_read_or_change_tenant_b(client: TestClient) -> None:
    first = client.post("/api/tenants", json=_body("acme", "admin@acme.example"))
    admin_token = _login(client, "admin@acme.example")
    second = client.post(
        "/api/tenants",
        json=_body("beta", "admin@beta.example", name="Beta"),
        headers=_auth(admin_token),
    )
    beta_id = second.json()["id"]
    acme_id = first.json()["id"]

    fetched = client.get(f"/api/tenants/{beta_id}", headers=_auth(admin_token))
    updated = client.patch(
        f"/api/tenants/{beta_id}",
        json={"name": "Taken"},
        headers=_auth(admin_token),
    )
    deleted = client.delete(f"/api/tenants/{beta_id}", headers=_auth(admin_token))
    assert fetched.status_code == 404
    assert updated.status_code == 404
    assert deleted.status_code == 404

    own = client.get(f"/api/tenants/{acme_id}", headers=_auth(admin_token))
    assert own.status_code == 200
    assert own.json()["id"] == acme_id

    listing = client.get("/api/tenants", headers=_auth(admin_token))
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [acme_id]


def test_user_lists_stay_inside_the_caller_tenant(client: TestClient) -> None:
    client.post("/api/tenants", json=_body("acme", "admin@acme.example"))
    acme_admin = _login(client, "admin@acme.example")
    client.post(
        "/api/users",
        json={"email": "manager@acme.example", "password": PASSWORD, "role": "MANAGER"},
        headers=_auth(acme_admin),
    )
    client.post(
        "/api/tenants",
        json=_body("beta", "admin@beta.example"),
        headers=_auth(acme_admin),
    )
    beta_admin = _login(client, "admin@beta.example")
    client.post(
        "/api/users",
        json={"email": "user@beta.example", "password": PASSWORD, "role": "USER"},
        headers=_auth(beta_admin),
    )

    acme_manager = _login(client, "manager@acme.example")
    beta_identity = client.get("/api/auth/me", headers=_auth(beta_admin))
    visible = client.get("/api/users", headers=_auth(acme_manager))
    assert visible.status_code == 200
    emails = {item["email"] for item in visible.json()}
    assert emails == {"admin@acme.example", "manager@acme.example"}
    assert all(item["tenant_id"] != beta_identity.json()["tenant_id"] for item in visible.json())

    user_token = _login(client, "user@beta.example")
    hidden = client.get("/api/users", headers=_auth(user_token))
    assert hidden.status_code == 403


def test_non_admin_cannot_update_or_delete_their_tenant(client: TestClient) -> None:
    created = client.post("/api/tenants", json=_body("acme", "admin@acme.example")).json()
    admin_token = _login(client, "admin@acme.example")
    client.post(
        "/api/users",
        json={"email": "user@acme.example", "password": PASSWORD, "role": "USER"},
        headers=_auth(admin_token),
    )
    user_token = _login(client, "user@acme.example")
    updated = client.patch(
        f"/api/tenants/{created['id']}",
        json={"name": "Nope"},
        headers=_auth(user_token),
    )
    deleted = client.delete(f"/api/tenants/{created['id']}", headers=_auth(user_token))
    assert updated.status_code == 403
    assert deleted.status_code == 403


def test_duplicate_slug_and_email_conflict(client: TestClient) -> None:
    client.post("/api/tenants", json=_body("acme", "admin@acme.example"))
    token = _login(client, "admin@acme.example")
    duplicate_slug = client.post(
        "/api/tenants",
        json=_body("acme", "other@acme.example"),
        headers=_auth(token),
    )
    duplicate_email = client.post(
        "/api/tenants",
        json=_body("other", "admin@acme.example"),
        headers=_auth(token),
    )
    assert duplicate_slug.status_code == 409
    assert duplicate_email.status_code == 409
