import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"
os.environ["JWT_SECRET_KEY"] = "test-secret"
os.environ["ENABLE_SCHEDULER"] = "false"  # evita levantar el job programado en cada test

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    def _register(slug: str = "acme-manufacturing", email: str = "admin@acme-manufacturing.com"):
        resp = client.post(
            "/auth/register",
            json={
                "tenant_name": "Acme Manufacturing",
                "tenant_slug": slug,
                "admin_email": email,
                "admin_password": "supersecret123",
            },
        )
        assert resp.status_code == 201, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
