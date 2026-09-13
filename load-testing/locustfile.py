"""Semana 9 — Prueba de carga sobre el endpoint de inferencia.

`@events.test_start` corre una sola vez (no por usuario simulado): registra
un tenant de carga, crea un activo y le carga las 5 lecturas AI4I que el
modelo necesita. Cada `InferenceUser` simulado reutiliza ese mismo activo
para golpear `POST /assets/{id}/predictions` repetidamente — es el endpoint
que importa medir (carga el modelo de MLflow y corre inferencia real), no el
CRUD alrededor.

Uso (contra el stack de docker-compose):
    uv run locust -f load-testing/locustfile.py --host http://localhost:8000

Headless, para capturar un número concreto:
    uv run locust -f load-testing/locustfile.py --host http://localhost:8000 \
        --headless -u 20 -r 5 -t 60s --csv load-testing/results
"""

from __future__ import annotations

import requests
from locust import HttpUser, between, events, task

EMAIL = "loadtest@predictmaint-loadtest.com"
PASSWORD = "loadtest12345"
TENANT_SLUG = "loadtest"

state: dict[str, str] = {}

READINGS = {
    "air_temperature": 301.5,
    "process_temperature": 311.2,
    "rotational_speed": 1350.0,
    "torque": 58.5,
    "tool_wear": 210.0,
}


@events.test_start.add_listener
def setup_load_test_fixture(environment, **kwargs) -> None:
    base = environment.host

    resp = requests.post(
        f"{base}/auth/register",
        json={
            "tenant_name": "Load Test Co",
            "tenant_slug": TENANT_SLUG,
            "admin_email": EMAIL,
            "admin_password": PASSWORD,
        },
        timeout=10,
    )
    if resp.status_code == 409:  # ya existe de una corrida anterior
        resp = requests.post(
            f"{base}/auth/login",
            data={"username": EMAIL, "password": PASSWORD},
            timeout=10,
        )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assets = requests.get(f"{base}/assets", headers=headers, timeout=10).json()
    if assets:
        asset_id = assets[0]["id"]
    else:
        asset = requests.post(
            f"{base}/assets",
            headers=headers,
            json={"name": "LoadTest-01", "asset_type": "cnc_milling_machine", "metadata": {"quality_variant": "M"}},
            timeout=10,
        ).json()
        asset_id = asset["id"]

    for sensor_name, value in READINGS.items():
        requests.post(
            f"{base}/assets/{asset_id}/readings",
            headers=headers,
            json={"time": "2026-01-01T00:00:00Z", "asset_id": asset_id, "sensor_name": sensor_name, "value": value},
            timeout=10,
        )

    state["token"] = token
    state["asset_id"] = asset_id
    print(f"[load-test] fixture lista: asset_id={asset_id}")


class InferenceUser(HttpUser):
    wait_time = between(0.2, 1.5)

    @task
    def predict_failure_probability(self) -> None:
        headers = {"Authorization": f"Bearer {state['token']}"}
        self.client.post(
            f"/assets/{state['asset_id']}/predictions",
            headers=headers,
            json={"prediction_type": "failure_probability"},
            name="/assets/[id]/predictions",
        )
