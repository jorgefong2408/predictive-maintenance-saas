def _create_asset(client, headers):
    resp = client.post(
        "/assets",
        headers=headers,
        json={"name": "Mill-07", "asset_type": "cnc_milling_machine", "metadata": {"quality_variant": "M"}},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_and_list_assets(client, auth_headers):
    headers = auth_headers()
    asset_id = _create_asset(client, headers)

    resp = client.get("/assets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == asset_id
    assert resp.json()[0]["status"] == "ok"


def test_ingest_and_list_readings(client, auth_headers):
    headers = auth_headers()
    asset_id = _create_asset(client, headers)

    resp = client.post(
        f"/assets/{asset_id}/readings",
        headers=headers,
        json={
            "time": "2026-01-01T00:00:00Z",
            "asset_id": asset_id,
            "sensor_name": "torque",
            "value": 42.0,
            "unit": "Nm",
        },
    )
    assert resp.status_code == 201

    resp = client.get(f"/assets/{asset_id}/readings", headers=headers)
    assert resp.status_code == 200
    readings = resp.json()
    assert len(readings) == 1
    assert readings[0]["sensor_name"] == "torque"
    assert readings[0]["value"] == 42.0


def test_list_readings_filters_by_sensor_name_and_since(client, auth_headers):
    headers = auth_headers()
    asset_id = _create_asset(client, headers)

    for time, sensor_name, value in [
        ("2026-01-01T00:00:00Z", "torque", 42.0),
        ("2026-01-01T00:00:00Z", "tool_wear", 10.0),
        ("2026-01-02T00:00:00Z", "torque", 45.0),
    ]:
        resp = client.post(
            f"/assets/{asset_id}/readings",
            headers=headers,
            json={"time": time, "asset_id": asset_id, "sensor_name": sensor_name, "value": value},
        )
        assert resp.status_code == 201

    resp = client.get(f"/assets/{asset_id}/readings", headers=headers, params={"sensor_name": "torque"})
    readings = resp.json()
    assert len(readings) == 2
    assert all(r["sensor_name"] == "torque" for r in readings)

    resp = client.get(f"/assets/{asset_id}/readings", headers=headers, params={"since": "2026-01-01T12:00:00Z"})
    readings = resp.json()
    assert len(readings) == 1
    assert readings[0]["value"] == 45.0


def test_readings_for_asset_of_other_tenant_returns_404(client, auth_headers):
    headers_a = auth_headers(slug="tenant-a", email="admin@tenant-a.com")
    headers_b = auth_headers(slug="tenant-b", email="admin@tenant-b.com")
    asset_id = _create_asset(client, headers_a)

    resp = client.post(
        f"/assets/{asset_id}/readings",
        headers=headers_b,
        json={
            "time": "2026-01-01T00:00:00Z",
            "asset_id": asset_id,
            "sensor_name": "torque",
            "value": 42.0,
        },
    )
    assert resp.status_code == 404
