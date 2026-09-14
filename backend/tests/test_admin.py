from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException

from app.core.security import create_access_token

MLFLOW_DB = Path(__file__).resolve().parents[2] / "ml" / "mlflow.db"

requires_trained_model = pytest.mark.skipif(
    not MLFLOW_DB.exists(),
    reason="Requiere el Model Registry de MLflow: correr uv run python ml/pipelines/train_ai4i_models.py",
)


@requires_trained_model
def test_list_model_versions(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/admin/models/ai4i-failure-classifier/versions", headers=headers)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 1
    assert any(v["is_champion"] for v in versions)
    assert "f1" in versions[0]["metrics"]


@requires_trained_model
def test_retrain_endpoint_reports_promotion_decision(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/admin/models/ai4i-failure-classifier/retrain", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "new_version" in body
    assert "promoted" in body
    assert isinstance(body["promoted"], bool)


def test_admin_endpoints_require_admin_role(client):
    resp = client.get("/admin/models/ai4i-failure-classifier/versions")
    assert resp.status_code == 401  # sin token


def test_non_admin_role_gets_403_not_401(client):
    """require_role("admin") — distinto de "sin token" (401): acá el token es
    válido, pero el rol no alcanza."""
    viewer_token = create_access_token(user_id="u1", tenant_id="t1", role="viewer")
    resp = client.get(
        "/admin/models/ai4i-failure-classifier/versions", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp.status_code == 403


def test_list_model_versions_404_when_model_does_not_exist(client, auth_headers):
    headers = auth_headers()
    with patch("app.api.admin.MlflowClient") as mock_client_cls:
        mock_client_cls.return_value.search_model_versions.side_effect = MlflowException("no existe")
        resp = client.get("/admin/models/no-existe/versions", headers=headers)
    assert resp.status_code == 404


def test_list_model_versions_without_a_champion_alias_yet(client, auth_headers):
    """Justo después de train_ai4i_models.py y antes del primer retrain.py
    (que fija el alias), get_model_version_by_alias lanza MlflowException —
    la respuesta debe listar igual las versiones, solo sin ninguna marcada
    is_champion."""
    headers = auth_headers()
    fake_version = MagicMock(version="1", run_id="run-1", creation_timestamp=0)
    with patch("app.api.admin.MlflowClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.search_model_versions.return_value = [fake_version]
        mock_client.get_model_version_by_alias.side_effect = MlflowException("sin alias todavía")
        mock_client.get_run.return_value.data.metrics = {"f1": 0.5}
        resp = client.get("/admin/models/ai4i-failure-classifier/versions", headers=headers)

    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["is_champion"] is False
