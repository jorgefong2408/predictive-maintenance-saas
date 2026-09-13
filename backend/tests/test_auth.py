def test_register_and_login(client, auth_headers):
    headers = auth_headers()

    resp = client.post(
        "/auth/login",
        data={"username": "admin@acme-manufacturing.com", "password": "supersecret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"

    # el token del registro ya sirve para llamar a un endpoint protegido
    resp = client.get("/assets", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_login_wrong_password(client, auth_headers):
    auth_headers()
    resp = client.post(
        "/auth/login",
        data={"username": "admin@acme-manufacturing.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_duplicate_tenant_slug_rejected(client, auth_headers):
    auth_headers(slug="acme-manufacturing", email="admin@acme-manufacturing.com")
    resp = client.post(
        "/auth/register",
        json={
            "tenant_name": "Acme Clone",
            "tenant_slug": "acme-manufacturing",
            "admin_email": "other@acme-manufacturing.com",
            "admin_password": "supersecret123",
        },
    )
    assert resp.status_code == 409


def test_protected_endpoint_requires_token(client):
    resp = client.get("/assets")
    assert resp.status_code == 401


def test_login_locks_out_after_max_failed_attempts(client, auth_headers):
    from app.api.auth import MAX_FAILED_ATTEMPTS

    auth_headers(slug="lockout-test", email="admin@lockout-test.com")

    for _ in range(MAX_FAILED_ATTEMPTS):
        resp = client.post(
            "/auth/login", data={"username": "admin@lockout-test.com", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    # el intento MAX_FAILED_ATTEMPTS+1 ya está bloqueado, aunque la contraseña sea correcta esta vez
    resp = client.post(
        "/auth/login", data={"username": "admin@lockout-test.com", "password": "supersecret123"}
    )
    assert resp.status_code == 429


def test_successful_login_resets_failed_attempt_counter(client, auth_headers):
    auth_headers(slug="reset-test", email="admin@reset-test.com")

    client.post("/auth/login", data={"username": "admin@reset-test.com", "password": "wrong-password"})
    client.post("/auth/login", data={"username": "admin@reset-test.com", "password": "wrong-password"})

    resp = client.post(
        "/auth/login", data={"username": "admin@reset-test.com", "password": "supersecret123"}
    )
    assert resp.status_code == 200

    # el contador se reseteó: 2 fallos más no deberían bloquear (el límite es MAX_FAILED_ATTEMPTS)
    resp = client.post("/auth/login", data={"username": "admin@reset-test.com", "password": "wrong-password"})
    assert resp.status_code == 401
