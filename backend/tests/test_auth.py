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
