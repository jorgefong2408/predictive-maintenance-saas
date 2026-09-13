from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> raíz del monorepo
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Bug de seguridad real: nada impedía arrancar en "producción" con el
# secreto de JWT default — un token falsificable por cualquiera que haya
# visto este mismo repo público. Ver el validador más abajo.
INSECURE_JWT_SECRETS = {"change-me", "change-me-in-prod"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "development" (default) no valida nada — así siguen funcionando el
    # dev local sin Docker y docker-compose.yml sin tocarlos. Solo
    # ENVIRONMENT=production (ver infra/k8s/04-backend.yaml) activa el check.
    environment: str = "development"

    # SQLite por defecto para desarrollo local sin Docker (ver README).
    # En Semana 8, docker-compose exporta DATABASE_URL apuntando a Postgres+TimescaleDB.
    # Este es el rol RESTRINGIDO (predictmaint_app, sin BYPASSRLS) — el que
    # sirve requests reales, sujeto a Row-Level Security (migración
    # 83dc2610fe35 crea el rol; sin esto, correr como el rol admin haría que
    # RLS no protegiera nada — un superusuario de Postgres SIEMPRE la salta,
    # el FORCE ROW LEVEL SECURITY de la tabla no cambia eso).
    database_url: str = "sqlite:///./predictmaint.db"

    # Rol ADMIN (superusuario), usado solo por Alembic/scripts/migrate_with_lock.py
    # para correr DDL (CREATE POLICY, CREATE ROLE, etc.) — nunca para servir
    # requests. Si no se define, cae a database_url (dev local sin Docker:
    # SQLite, un solo rol, no aplica la separación).
    migration_database_url: str | None = None

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @model_validator(mode="after")
    def _reject_insecure_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.jwt_secret_key in INSECURE_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY no puede ser el valor default con ENVIRONMENT=production. "
                "Generar uno real, ej.: openssl rand -hex 32"
            )
        return self

    # Rutas absolutas: la API puede arrancar desde cualquier cwd y debe
    # encontrar el mismo registro de modelos que usan los pipelines de ml/.
    mlflow_tracking_uri: str = f"sqlite:///{PROJECT_ROOT / 'ml' / 'mlflow.db'}"

    # Semana 7: job programado de reentrenamiento (ver app/services/scheduler.py)
    enable_scheduler: bool = True
    retrain_interval_hours: int = 24

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
