"""Carga los datos procesados (parquet) a Postgres/TimescaleDB.

Requiere que `infra/sql/001_schema.sql` ya se haya aplicado sobre la base
(ver infra/docker-compose.yml, Semana 8, o cualquier Postgres+TimescaleDB
accesible) y que exista al menos el tenant demo `acme-manufacturing`.

Uso:
    export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/predictmaint
    uv run python ml/pipelines/load_to_postgres.py
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
DEMO_TENANT_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "acme-manufacturing.predictmaint")


def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Define DATABASE_URL, ej: postgresql+psycopg2://user:pass@localhost:5432/predictmaint")
    return create_engine(url)


def ensure_demo_tenant(conn) -> None:
    conn.execute(
        text(
            """
            INSERT INTO tenants (id, name, slug, plan)
            VALUES (:id, :name, :slug, 'pro')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": str(DEMO_TENANT_ID), "name": "Acme Manufacturing", "slug": "acme-manufacturing"},
    )


def load_assets(conn, assets: pd.DataFrame) -> None:
    for _, row in assets.iterrows():
        conn.execute(
            text(
                """
                INSERT INTO assets (id, tenant_id, name, asset_type, external_ref, status, metadata)
                VALUES (:id, :tenant_id, :name, :asset_type, :external_ref, :status,
                        jsonb_build_object('quality_variant', :quality_variant))
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": row["asset_id"],
                "tenant_id": row["tenant_id"],
                "name": row["name"],
                "asset_type": row["asset_type"],
                "external_ref": row["external_ref"],
                "status": row["status"],
                "quality_variant": row["quality_variant"],
            },
        )


def load_sensor_readings(conn, readings: pd.DataFrame) -> None:
    readings.to_sql("sensor_readings", conn, if_exists="append", index=False, method="multi", chunksize=5000)


def load_failure_events(conn, failures: pd.DataFrame) -> None:
    for _, row in failures.iterrows():
        conn.execute(
            text(
                """
                INSERT INTO failure_events (id, tenant_id, asset_id, occurred_at, failure_type, source)
                VALUES (:id, :tenant_id, :asset_id, :occurred_at, :failure_type, :source)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": row["event_id"],
                "tenant_id": row["tenant_id"],
                "asset_id": row["asset_id"],
                "occurred_at": row["occurred_at"],
                "failure_type": row["failure_type"],
                "source": row["source"],
            },
        )


def main() -> None:
    engine = get_engine()
    assets = pd.read_parquet(PROCESSED_DIR / "assets.parquet")
    readings = pd.read_parquet(PROCESSED_DIR / "sensor_readings.parquet")
    failures = pd.read_parquet(PROCESSED_DIR / "failure_events.parquet")

    with engine.begin() as conn:
        # assets/sensor_readings/failure_events tienen Row-Level Security
        # (backend/alembic/versions/83dc2610fe35_*.py): sin fijar esto, Postgres
        # rechaza los INSERT de este script (que no pasa por la API/FastAPI,
        # donde normalmente se fija por request — ver app/api/deps.py).
        # `false` (no "is_local"): esta conexión hace todo su trabajo en esta
        # única transacción/bloque, no hace falta que se resetee sola antes.
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": str(DEMO_TENANT_ID)}
        )
        ensure_demo_tenant(conn)
        load_assets(conn, assets)
        load_failure_events(conn, failures)
        load_sensor_readings(conn, readings)

    print(f"Cargados: {len(assets)} assets, {len(readings)} sensor_readings, {len(failures)} failure_events")


if __name__ == "__main__":
    main()
