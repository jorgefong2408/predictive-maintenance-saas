"""Semana 9 — prueba end-to-end del flujo completo del producto.

A diferencia de los tests unitarios/de integración de test_*.py (cada uno
verifica una pieza), este recorre la historia completa en un solo test,
en el mismo orden que un operador real la viviría: UC3 (alta de tenant) ->
UC4 (alta de activo + ciclo de vida) -> UC1 (ingesta -> predicción real vía
MLflow -> alerta automática -> reconocimiento) -> UC6 (trazabilidad de la
predicción). Si algo en la cadena se rompe, este test falla aunque cada
pieza individual siga pasando por separado.
"""

from pathlib import Path

import pytest

MLFLOW_DB = Path(__file__).resolve().parents[2] / "ml" / "mlflow.db"

requires_trained_model = pytest.mark.skipif(
    not MLFLOW_DB.exists(),
    reason="Requiere el Model Registry de MLflow: correr uv run python ml/pipelines/train_ai4i_models.py",
)


@requires_trained_model
def test_full_product_flow(client, auth_headers):
    # UC3: alta de tenant + admin
    headers = auth_headers(slug="e2e-acme", email="admin@e2e-acme.com")

    # UC4: alta de activo, arranca en estado "ok"
    resp = client.post(
        "/assets",
        headers=headers,
        json={"name": "Mill-E2E", "asset_type": "cnc_milling_machine", "metadata": {"quality_variant": "M"}},
    )
    assert resp.status_code == 201
    asset = resp.json()
    assert asset["status"] == "ok"
    asset_id = asset["id"]

    # UC1: ingesta de las 5 lecturas AI4I, con valores de alto riesgo
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
            json={"time": "2026-01-01T00:00:00Z", "asset_id": asset_id, "sensor_name": sensor_name, "value": value},
        )
        assert resp.status_code == 201

    resp = client.get(f"/assets/{asset_id}/readings", headers=headers)
    assert len(resp.json()) == 5

    # UC1: predicción real (carga el modelo desde MLflow, no un mock)
    resp = client.post(
        f"/assets/{asset_id}/predictions",
        headers=headers,
        json={"prediction_type": "failure_probability"},
    )
    assert resp.status_code == 201
    prediction = resp.json()
    assert 0.0 <= prediction["value"] <= 1.0
    assert prediction["model_name"] == "ai4i-failure-classifier"

    # UC1: el riesgo alto disparó una alerta automática y subió el status del activo
    resp = client.get(f"/assets/{asset_id}", headers=headers)
    assert resp.json()["status"] in ("warning", "critical")

    resp = client.get("/alerts", headers=headers)
    alerts = resp.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["asset_id"] == asset_id
    assert alert["acknowledged_at"] is None

    # Reconocer la alerta: queda "vista" pero no resuelta (son conceptos distintos)
    resp = client.post(f"/alerts/{alert['id']}/acknowledge", headers=headers)
    assert resp.status_code == 200
    acknowledged = resp.json()
    assert acknowledged["acknowledged_at"] is not None
    assert acknowledged["resolved_at"] is None

    # todavía cuenta como "activa" (active_only=true) porque no está resuelta
    resp = client.get("/alerts", headers=headers, params={"active_only": True})
    assert len(resp.json()) == 1

    # UC6: trazabilidad — la predicción queda en el historial del activo
    resp = client.get(f"/assets/{asset_id}/predictions", headers=headers)
    history = resp.json()
    assert len(history) == 1
    assert history[0]["id"] == prediction["id"]
