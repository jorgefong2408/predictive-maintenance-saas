"""Pub/sub en memoria para el panel de alertas en tiempo real (UC1, Semana 6).

Simplificación deliberada para esta fase: un solo proceso uvicorn mantiene
las conexiones WebSocket y las alertas se generan en el mismo proceso
(app/api/predictions.py), así que un dict en memoria basta. Si el backend
llega a correr con múltiples workers/réplicas (Semana 8), esto debe migrar a
un pub/sub compartido (Redis) — ya está en el stack del plan para Celery.
"""

from __future__ import annotations

import asyncio

from starlette.websockets import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, tenant_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(tenant_id, set()).add(websocket)

    def disconnect(self, tenant_id: str, websocket: WebSocket) -> None:
        self._connections.get(tenant_id, set()).discard(websocket)

    async def _broadcast(self, tenant_id: str, message: dict) -> None:
        dead = []
        for ws in self._connections.get(tenant_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[tenant_id].discard(ws)

    def broadcast_threadsafe(self, tenant_id: str, message: dict) -> None:
        """Los endpoints REST son síncronos (SQLAlchemy sync); esto permite
        despachar al loop async del servidor WebSocket desde ese hilo."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(tenant_id, message), self._loop)


manager = ConnectionManager()
