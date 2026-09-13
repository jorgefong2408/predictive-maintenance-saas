from pathlib import Path

import pytest

MLFLOW_DB = Path(__file__).resolve().parents[2] / "ml" / "mlflow.db"

requires_trained_model = pytest.mark.skipif(
    not MLFLOW_DB.exists(),
    reason="Requiere el Model Registry de MLflow: correr uv run python ml/pipelines/train_ai4i_models.py",
)


def _create_asset_with_readings(client, headers):
    resp = client.post(
        "/assets",
        headers=headers,
        json={"name": "Mill-07", "asset_type": "cnc_milling_machine", "metadata": {"quality_variant": "M"}},
    )
    asset_id = resp.json()["id"]

    readings = {
        "air_temperature": 301.5,
        "process_temperature": 311.2,
        "rotational_speed": 1350.0,
        "torque": 58.5,
        "tool_wear": 210.0,
    }
    for sensor_name, value in readings.items():
        resp = client.post(
            f"/assets/{asset_id}/readings",
            headers=headers,
            json={
                "time": "2026-01-01T00:00:00Z",
                "asset_id": asset_id,
                "sensor_name": sensor_name,
                "value": value,
            },
        )
        assert resp.status_code == 201
    return asset_id


@requires_trained_model
def test_predict_failure_probability_creates_alert_when_high_risk(client, auth_headers):
    headers = auth_headers()
    asset_id = _create_asset_with_readings(client, headers)

    resp = client.post(
        f"/assets/{asset_id}/predictions",
        headers=headers,
        json={"prediction_type": "failure_probability"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["model_name"] == "ai4i-failure-classifier"
    assert 0.0 <= body["value"] <= 1.0

    # las lecturas usadas (torque y tool_wear altos) son de riesgo, deben disparar alerta
    resp = client.get("/alerts", headers=headers)
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) == 1
    assert alerts[0]["asset_id"] == asset_id
    assert alerts[0]["severity"] in ("warning", "critical")


def test_predict_without_readings_returns_422(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/assets", headers=headers, json={"name": "Mill-08", "asset_type": "cnc_milling_machine"})
    asset_id = resp.json()["id"]

    resp = client.post(
        f"/assets/{asset_id}/predictions",
        headers=headers,
        json={"prediction_type": "failure_probability"},
    )
    assert resp.status_code == 422


def test_rul_prediction_not_implemented_yet(client, auth_headers):
    headers = auth_headers()
    resp = client.post("/assets", headers=headers, json={"name": "Mill-09", "asset_type": "cnc_milling_machine"})
    asset_id = resp.json()["id"]

    resp = client.post(
        f"/assets/{asset_id}/predictions",
        headers=headers,
        json={"prediction_type": "rul_days"},
    )
    assert resp.status_code == 501
