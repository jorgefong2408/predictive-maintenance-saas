from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import InvalidTokenError, decode_access_token
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/alerts")
async def alerts_stream(websocket: WebSocket, token: str) -> None:
    """El WebSocket nativo del navegador no permite headers custom, así que
    el JWT viaja como query param (?token=...) en vez de Authorization."""
    try:
        claims = decode_access_token(token)
    except InvalidTokenError:
        await websocket.close(code=4401)
        return

    tenant_id = claims["tenant_id"]
    await manager.connect(tenant_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # el cliente no envía nada; solo detecta desconexión
    except WebSocketDisconnect:
        manager.disconnect(tenant_id, websocket)
