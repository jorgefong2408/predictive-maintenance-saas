from pathlib import Path

import pytest

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
