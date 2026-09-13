"""Pub/sub para el panel de alertas en tiempo real (UC1, Semana 6).

Cada réplica del backend (`infra/k8s/04-backend.yaml` corre 2) mantiene sus
propias conexiones WebSocket en memoria — eso nunca deja de ser así, un
cliente siempre está conectado a UNA réplica concreta. Lo que sí tiene que
viajar entre réplicas es el AVISO de que hay una alerta nueva: si la réplica
A la crea pero el cliente está conectado a la réplica B, B nunca se entera
sin algo compartido. Se usa Postgres LISTEN/NOTIFY para eso (ver
`notify_alert` y `PostgresListener`) — evita sumar Redis solo para esto,
igual que la decisión del scheduler (Celery beat "o cron").

En SQLite (dev local sin Docker, un solo proceso) no hace falta nada de esto:
`app/api/predictions.py` sigue llamando `broadcast_threadsafe` directo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import select
import threading

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "predictmaint_alerts"


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
        """Entrega SOLO a los clientes conectados a esta réplica. Los
        endpoints REST son síncronos (SQLAlchemy sync); esto permite
        despachar al loop async del servidor WebSocket desde ese hilo."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(tenant_id, message), self._loop)


manager = ConnectionManager()


def notify_alert(conn, tenant_id: str, message: dict) -> None:
    """Publica el aviso para que TODAS las réplicas lo reciban (vía sus
    PostgresListener) y lo entreguen a sus propios clientes conectados,
    incluida la réplica que hizo esta llamada. `conn` es una conexión/sesión
    de SQLAlchemy ya abierta (reusa la transacción del request en curso)."""
    from sqlalchemy import text

    payload = json.dumps({"tenant_id": tenant_id, "message": message})
    conn.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": NOTIFY_CHANNEL, "payload": payload})


class PostgresListener:
    """Un hilo por réplica que escucha NOTIFY y reenvía a broadcast_threadsafe
    (que ya sabe entregar solo a las conexiones locales de esta réplica)."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="postgres-listener")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        import psycopg2
        import psycopg2.extensions

        # SQLAlchemy URLs vienen como "postgresql+psycopg2://...";
        # psycopg2.connect necesita el dialecto plano.
        dsn = self._database_url.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(dsn)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"LISTEN {NOTIFY_CHANNEL};")
        logger.info("PostgresListener escuchando en %s", NOTIFY_CHANNEL)

        try:
            while not self._stop_event.is_set():
                if not select.select([conn], [], [], 5)[0]:
                    continue
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    try:
                        payload = json.loads(notify.payload)
                        manager.broadcast_threadsafe(payload["tenant_id"], payload["message"])
                    except Exception:
                        logger.exception("No se pudo procesar una notificación de Postgres")
        finally:
            conn.close()
