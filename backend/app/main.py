import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api import admin, alerts, assets, auth, predictions, readings, ws
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging
from app.core.security import InvalidTokenError, decode_access_token
from app.services import scheduler
from app.services.ws_manager import PostgresListener, manager

settings = get_settings()
configure_logging(settings.log_level)
access_logger = logging.getLogger("app.access")
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)

    # Best-effort: solo para enriquecer el log (poder filtrar por tenant en
    # Loki/Grafana). Un token ausente/inválido no debe afectar la respuesta
    # real, que ya la decidió (o rechazó) el Depends() de la ruta.
    tenant_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            tenant_id = decode_access_token(auth_header[7:]).get("tenant_id")
        except InvalidTokenError:
            pass

    access_logger.info(
        "http_request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "tenant_id": tenant_id,
        },
    )
    return response

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
