"""/ws/alerts (app/api/ws.py) tenía 33% de cobertura — nunca se probó con
pytest, solo a mano en el navegador. TestClient soporta WebSockets de
verdad (no un doble), así que esto ejercita el endpoint real."""

import pytest
from starlette.websockets import WebSocketDisconnect

from app.services.ws_manager import manager


def test_ws_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/alerts?token=un-token-invalido"):
            pass
    assert exc_info.value.code == 4401


def test_ws_accepts_valid_token_and_registers_connection(client, auth_headers):
    headers = auth_headers()
    token = headers["Authorization"].split(" ")[1]

    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        assert ws is not None  # si el token fuera inválido, el connect de arriba ya habría fallado


def test_ws_delivers_broadcast_messages_to_the_connected_tenant(client, auth_headers):
    headers = auth_headers()
    token = headers["Authorization"].split(" ")[1]

    with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
        manager.broadcast_threadsafe(
            headers_tenant_id(token), {"type": "alert", "alert": {"id": "test-alert"}}
        )
        message = ws.receive_json()
        assert message == {"type": "alert", "alert": {"id": "test-alert"}}


def test_ws_disconnect_removes_the_connection_from_the_manager(client, auth_headers):
    headers = auth_headers()
    token = headers["Authorization"].split(" ")[1]
    tenant_id = headers_tenant_id(token)

    with client.websocket_connect(f"/ws/alerts?token={token}"):
        assert len(manager._connections.get(tenant_id, set())) == 1

    # al salir del "with" el cliente cierra la conexión; el servidor debe notarlo
    assert len(manager._connections.get(tenant_id, set())) == 0


def headers_tenant_id(token: str) -> str:
    import base64
    import json

    payload = token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))["tenant_id"]
