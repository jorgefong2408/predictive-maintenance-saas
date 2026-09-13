def test_tenant_cannot_see_another_tenants_assets(client, auth_headers):
    """UC3 del plan: aislamiento multi-tenant."""
    headers_a = auth_headers(slug="acme-manufacturing", email="admin@acme-manufacturing.com")
    headers_b = auth_headers(slug="borealis-industrial", email="admin@borealis-industrial.com")

    resp = client.post(
        "/assets",
        headers=headers_a,
        json={"name": "Mill-07", "asset_type": "cnc_milling_machine"},
    )
    assert resp.status_code == 201
    asset_id = resp.json()["id"]

    resp = client.get("/assets", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get(f"/assets/{asset_id}", headers=headers_b)
    assert resp.status_code == 404

    resp = client.get(f"/assets/{asset_id}", headers=headers_a)
    assert resp.status_code == 200
