from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.api import alerts, assets, auth, predictions, readings
from app.core.config import get_settings
from app.core.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url.startswith("sqlite"):
        # Desarrollo local sin Docker (ver README): crea el esquema directo.
        # En Postgres, las migraciones de Alembic (backend/alembic/) son la fuente de verdad.
        Base.metadata.create_all(bind=engine)
    yield


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
