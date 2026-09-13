from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> raíz del monorepo
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite por defecto para desarrollo local sin Docker (ver README).
    # En Semana 8, docker-compose exporta DATABASE_URL apuntando a Postgres+TimescaleDB.
    database_url: str = "sqlite:///./predictmaint.db"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Rutas absolutas: la API puede arrancar desde cualquier cwd y debe
    # encontrar el mismo registro de modelos que usan los pipelines de ml/.
    mlflow_tracking_uri: str = f"sqlite:///{PROJECT_ROOT / 'ml' / 'mlflow.db'}"
    ai4i_model_uri: str = "models:/ai4i-failure-classifier/1"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
