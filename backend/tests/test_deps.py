"""app/api/deps.py::get_tenant_scoped_db ya se probó a fondo contra Postgres
real (ver README, sección "Seguridad") — esto cubre la rama Postgres con un
AsyncSession de mentira, para que quede protegida en cada `pytest` sin
depender de tener Docker corriendo."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import Claims, get_tenant_scoped_db


def test_sets_and_resets_tenant_context_on_postgres():
    fake_db = AsyncMock()
    fake_db.bind = MagicMock()
    fake_db.bind.dialect.name = "postgresql"
    claims = Claims(user_id="u1", tenant_id="tenant-a", role="admin")

    async def run():
        gen = get_tenant_scoped_db(claims=claims, db=fake_db)
        yielded = await gen.__anext__()
        assert yielded is fake_db

        # primera llamada: fija el tenant actual
        set_call = fake_db.execute.call_args_list[0]
        assert "set_config" in str(set_call.args[0])
        assert set_call.args[1] == {"tid": "tenant-a"}

        # al cerrar el generador (fin del request) debe resetear y commitear
        await gen.aclose()
        reset_call = fake_db.execute.call_args_list[1]
        assert "set_config" in str(reset_call.args[0])
        fake_db.commit.assert_called_once()

    asyncio.run(run())


def test_does_nothing_extra_on_sqlite():
    fake_db = AsyncMock()
    fake_db.bind = MagicMock()
    fake_db.bind.dialect.name = "sqlite"
    claims = Claims(user_id="u1", tenant_id="tenant-a", role="admin")

    async def run():
        gen = get_tenant_scoped_db(claims=claims, db=fake_db)
        await gen.__anext__()
        await gen.aclose()

    asyncio.run(run())

    fake_db.execute.assert_not_called()
