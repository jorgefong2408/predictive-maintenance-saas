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


def test_duplicate_email_across_different_tenants_rejected(client, auth_headers):
    """Distinto del slug duplicado: acá el tenant es nuevo, pero el email del
    admin ya existe en OTRO tenant — el email es único globalmente (ver
    docs/DATA_SCHEMA.md)."""
    auth_headers(slug="tenant-one", email="shared@example.com")
    resp = client.post(
        "/auth/register",
        json={
            "tenant_name": "Tenant Two",
            "tenant_slug": "tenant-two",
            "admin_email": "shared@example.com",
            "admin_password": "supersecret123",
        },
    )
    assert resp.status_code == 409


def test_protected_endpoint_requires_token(client):
    resp = client.get("/assets")
    assert resp.status_code == 401


def test_malformed_token_returns_401_not_500(client):
    """Distinto de 'sin token': acá viaja un valor cualquiera en el header
    Authorization — decode_access_token debe rechazarlo con InvalidTokenError,
    no dejar que la excepción de jose se propague como un 500."""
    resp = client.get("/assets", headers={"Authorization": "Bearer esto-no-es-un-jwt"})
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


def test_failed_attempt_window_resets_after_it_expires(client, auth_headers):
    """Distinto del reset por login exitoso: acá la ventana de 15 min vence
    sola entre dos intentos fallidos — el contador debe arrancar de nuevo
    en vez de acumular sobre una ventana vieja."""
    from datetime import UTC, datetime, timedelta

    from app.api.auth import ATTEMPT_WINDOW_MINUTES, MAX_FAILED_ATTEMPTS
    from app.core.database import SessionLocal
    from app.models.login_attempt import LoginAttempt

    auth_headers(slug="window-expiry-test", email="admin@window-expiry-test.com")
    client.post(
        "/auth/login", data={"username": "admin@window-expiry-test.com", "password": "wrong-password"}
    )

    db = SessionLocal()
    attempt = db.query(LoginAttempt).filter(LoginAttempt.email == "admin@window-expiry-test.com").first()
    attempt.window_started_at = datetime.now(UTC) - timedelta(minutes=ATTEMPT_WINDOW_MINUTES + 1)
    db.commit()
    db.close()

    # si la ventana no se hubiera reseteado, este sería el intento #2 y
    # llegar a MAX_FAILED_ATTEMPTS tomaría uno menos de lo esperado
    for _ in range(MAX_FAILED_ATTEMPTS - 1):
        resp = client.post(
            "/auth/login", data={"username": "admin@window-expiry-test.com", "password": "wrong-password"}
        )
        assert resp.status_code == 401

    resp = client.post(
        "/auth/login", data={"username": "admin@window-expiry-test.com", "password": "supersecret123"}
    )
    assert resp.status_code == 200  # todavía no debería estar bloqueado


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
