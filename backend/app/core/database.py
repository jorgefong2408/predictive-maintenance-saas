from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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
engine = create_engine(settings.database_url, connect_args=connect_args, **pool_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
