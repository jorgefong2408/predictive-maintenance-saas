"""app/services/ws_manager.py tenía la cobertura más baja del backend (43%):
se probó a mano en el navegador (Semana 6) y contra Postgres real con un
script (Semana 8), pero nunca quedó protegido por un test automático. Estos
sí corren en cada `pytest` — sin necesidad de un WebSocket real ni de
Postgres, con dobles simples que imitan lo mínimo que el código usa de cada
uno."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from app.services.ws_manager import NOTIFY_CHANNEL, ConnectionManager, PostgresListener, notify_alert


class FakeWebSocket:
    """No hace falta un WebSocket real: `connect`/`_broadcast` solo llaman a
    `.accept()` y `.send_json()`."""

    def __init__(self, fail_on_send: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self.fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self.fail_on_send:
            raise ConnectionError("cliente desconectado")
        self.sent.append(message)


def test_connect_accepts_and_registers_the_websocket():
    manager = ConnectionManager()
    ws = FakeWebSocket()

    asyncio.run(manager.connect("tenant-a", ws))

    assert ws.accepted
    assert ws in manager._connections["tenant-a"]


def test_disconnect_removes_the_websocket():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    asyncio.run(manager.connect("tenant-a", ws))

    manager.disconnect("tenant-a", ws)

    assert ws not in manager._connections["tenant-a"]


def test_disconnect_of_unknown_tenant_does_not_raise():
    manager = ConnectionManager()
    manager.disconnect("never-connected", FakeWebSocket())  # no debe explotar


def test_broadcast_delivers_only_to_the_matching_tenant():
    manager = ConnectionManager()
    ws_a = FakeWebSocket()
    ws_b = FakeWebSocket()
    asyncio.run(manager.connect("tenant-a", ws_a))
    asyncio.run(manager.connect("tenant-b", ws_b))

    asyncio.run(manager._broadcast("tenant-a", {"type": "alert"}))

    assert ws_a.sent == [{"type": "alert"}]
    assert ws_b.sent == []


def test_broadcast_drops_dead_connections_without_failing_the_others():
    manager = ConnectionManager()
    dead = FakeWebSocket(fail_on_send=True)
    alive = FakeWebSocket()
    asyncio.run(manager.connect("tenant-a", dead))
    asyncio.run(manager.connect("tenant-a", alive))

    asyncio.run(manager._broadcast("tenant-a", {"type": "alert"}))

    assert alive.sent == [{"type": "alert"}]
    assert dead not in manager._connections["tenant-a"]  # se limpió sola


def test_broadcast_threadsafe_is_a_noop_before_bind_loop():
    """Antes de que main.py llame bind_loop() en el startup, no hay loop al
    que despachar — no debe explotar, solo no hacer nada."""
    manager = ConnectionManager()
    manager.broadcast_threadsafe("tenant-a", {"type": "alert"})  # no debe lanzar


def test_broadcast_threadsafe_dispatches_to_the_bound_loop():
    manager = ConnectionManager()
    ws = FakeWebSocket()
    asyncio.run(manager.connect("tenant-a", ws))

    async def run_and_dispatch():
        loop = asyncio.get_running_loop()
        manager.bind_loop(loop)
        manager.broadcast_threadsafe("tenant-a", {"type": "alert"})
        await asyncio.sleep(0.05)  # deja correr la tarea despachada

    asyncio.run(run_and_dispatch())

    assert ws.sent == [{"type": "alert"}]


def test_notify_alert_publishes_via_pg_notify_with_json_payload():
    conn = MagicMock()

    notify_alert(conn, "tenant-a", {"type": "alert", "alert": {"id": "1"}})

    conn.execute.assert_called_once()
    (stmt, params), _ = conn.execute.call_args
    assert str(stmt) == "SELECT pg_notify(:channel, :payload)"
    assert params["channel"] == NOTIFY_CHANNEL
    assert json.loads(params["payload"]) == {
        "tenant_id": "tenant-a",
        "message": {"type": "alert", "alert": {"id": "1"}},
    }


def test_postgres_listener_start_spawns_a_daemon_thread():
    listener = PostgresListener("postgresql+psycopg2://u:p@localhost/db")
    with patch.object(PostgresListener, "_run", return_value=None):
        listener.start()
        assert listener._thread is not None
        assert listener._thread.daemon is True
        listener.stop()


def test_postgres_listener_stop_signals_and_joins():
    listener = PostgresListener("postgresql+psycopg2://u:p@localhost/db")

    def fake_run():
        listener._stop_event.wait()  # se queda "escuchando" hasta que stop() avise

    with patch.object(PostgresListener, "_run", side_effect=fake_run):
        listener.start()
        assert not listener._stop_event.is_set()
        listener.stop()
        assert listener._stop_event.is_set()
        assert not listener._thread.is_alive()


def test_postgres_listener_run_forwards_notifications_to_broadcast():
    """Simula lo que psycopg2 le daría al loop de _run tras un NOTIFY real,
    sin necesitar Postgres — confirma que decodifica el payload y llama a
    broadcast_threadsafe con (tenant_id, message)."""
    fake_notify = MagicMock(payload=json.dumps({"tenant_id": "tenant-a", "message": {"type": "alert"}}))

    fake_conn = MagicMock()
    fake_conn.notifies = [fake_notify]

    listener = PostgresListener("postgresql+psycopg2://u:p@localhost/db")
    calls = []

    def stop_after_one_notification(*args, **kwargs):
        # select.select(...) -> primera vuelta "hay datos", segunda vuelta corta el loop
        if not calls:
            calls.append(1)
            return ([fake_conn], [], [])
        listener._stop_event.set()
        return ([], [], [])

    with (
        patch("psycopg2.connect", return_value=fake_conn),
        patch("psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT", 0),
        patch("select.select", side_effect=stop_after_one_notification),
        patch("app.services.ws_manager.manager.broadcast_threadsafe") as mock_broadcast,
    ):
        listener._run()

    mock_broadcast.assert_called_once_with("tenant-a", {"type": "alert"})
    fake_conn.close.assert_called_once()


def test_postgres_listener_run_survives_a_malformed_notification():
    """Un NOTIFY con un payload corrupto (nunca debería pasar si solo lo
    publica notify_alert, pero Postgres no lo garantiza) no debe tumbar el
    hilo entero — se loguea y se sigue escuchando."""
    bad_notify = MagicMock(payload="esto no es json")
    good_notify = MagicMock(payload=json.dumps({"tenant_id": "tenant-a", "message": {"type": "alert"}}))

    fake_conn = MagicMock()
    fake_conn.notifies = [bad_notify, good_notify]

    listener = PostgresListener("postgresql+psycopg2://u:p@localhost/db")
    calls = []

    def stop_after_one_batch(*args, **kwargs):
        if not calls:
            calls.append(1)
            return ([fake_conn], [], [])
        listener._stop_event.set()
        return ([], [], [])

    with (
        patch("psycopg2.connect", return_value=fake_conn),
        patch("psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT", 0),
        patch("select.select", side_effect=stop_after_one_batch),
        patch("app.services.ws_manager.manager.broadcast_threadsafe") as mock_broadcast,
    ):
        listener._run()  # no debe propagar la excepción del payload corrupto

    # el mensaje bueno que venía después del corrupto igual se procesó
    mock_broadcast.assert_called_once_with("tenant-a", {"type": "alert"})
