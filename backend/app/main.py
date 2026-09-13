import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api import admin, alerts, assets, auth, predictions, readings, ws
from app.core.config import get_settings
from app.core.database import Base, engine
from app.services import scheduler
from app.services.ws_manager import PostgresListener, manager

settings = get_settings()
_postgres_listener: PostgresListener | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _postgres_listener
    if settings.database_url.startswith("sqlite"):
        # Desarrollo local sin Docker (ver README): crea el esquema directo.
        # En Postgres, las migraciones de Alembic (backend/alembic/) son la fuente de verdad.
        Base.metadata.create_all(bind=engine)
    else:
        # Multi-réplica: entrega alertas a clientes conectados a OTRAS
        # réplicas (ver app/services/ws_manager.py).
        _postgres_listener = PostgresListener(settings.database_url)
        _postgres_listener.start()
    manager.bind_loop(asyncio.get_running_loop())
    scheduler.start()
    yield
    scheduler.stop()
    if _postgres_listener is not None:
        _postgres_listener.stop()


app = FastAPI(title="Predictive Maintenance SaaS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assets.router)
app.include_router(readings.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(admin.router)
app.include_router(ws.router)

# Semana 9: métricas de sistema (latencia, throughput, tasa de error por
# endpoint) en /metrics, formato Prometheus. Ver docker-compose.yml (prometheus
# scrapea este endpoint) e infra/observability/grafana para el dashboard.
Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
