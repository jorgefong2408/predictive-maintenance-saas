from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
# Pool default de SQLAlchemy (5 + 10 overflow) se quedaba corto bajo carga
# concurrente (Semana 9, ver load-testing/RESULTS.md): cada predicción hace
# varias idas a la base (leer lecturas, insertar predicción, insertar
# alerta), y con 20 requests simultáneos la mayoría termina esperando una
# conexión libre. SQLite no tiene este concepto de pool de conexiones TCP.
pool_kwargs = {} if is_sqlite else {"pool_size": 20, "max_overflow": 20}


def _to_async_url(url: str) -> str:
    """DATABASE_URL sigue siendo el mismo string síncrono de siempre
    (postgresql+psycopg2://... o sqlite:///...) -- no hace falta una variable
    de entorno nueva ni tocar docker-compose.yml/K8s. Se deriva la variante
    async solo cambiando el driver."""
    if url.startswith("sqlite"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1).replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


# Motor ASYNC: el que sirve el ciclo request/response real de FastAPI (ver
# app/api/deps.py::get_db). asyncpg/aiosqlite en vez de psycopg2/pysqlite.
async_engine = create_async_engine(_to_async_url(settings.database_url), connect_args=connect_args, **pool_kwargs)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Bug real encontrado migrando a async: un Session bindeado directo al
    engine (`async_sessionmaker(async_engine)()` a secas) puede devolver la
    conexión física al pool en cada `commit()` -- el siguiente statement
    (ej. un `db.refresh()`) toma otra conexión del pool que no tiene seteado
    `app.current_tenant_id` (ver app/api/deps.py::get_tenant_scoped_db), y
    la política RLS de SELECT bloquea la relectura ("Could not refresh
    instance", aunque el INSERT sí había committeado bien -- el problema era
    de lectura, no de escritura). Checkear la conexión una vez por request y
    bindear el Session a ESA conexión (no al engine) garantiza que sea la
    misma durante todos los commits del request, sin importar cómo el pool
    decida reciclar conexiones entre requests distintos."""
    async with async_engine.connect() as conn:
        async with AsyncSession(bind=conn, expire_on_commit=False, autoflush=False) as db:
            yield db


# Motor SÍNCRONO aparte -- para lo que corre FUERA del ciclo request/response
# y no tiene nada que ganar volviéndose async: el scheduler de reentrenamiento
# (app/services/scheduler.py, un BackgroundScheduler en su propio hilo de SO)
# y los tests que arman/leen datos directo contra la base (ver
# backend/tests/conftest.py y test_auth.py). Alembic y
# scripts/migrate_with_lock.py ya tienen su propio engine independiente (ver
# alembic/env.py) -- no dependen de ninguno de los dos motores de este archivo.
# Como ya no sirve tráfico real de la API, un pool grande sería desperdiciado
# (el scheduler usa como mucho 1 conexión a la vez).
sync_pool_kwargs = {} if is_sqlite else {"pool_size": 2, "max_overflow": 3}
engine = create_engine(settings.database_url, connect_args=connect_args, **sync_pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
