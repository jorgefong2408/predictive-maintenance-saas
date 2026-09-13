"""Envoltorio de `alembic upgrade head` con un advisory lock de Postgres.

Bug real encontrado en revisión: `infra/k8s/04-backend.yaml` corre esta
migración en un initContainer POR RÉPLICA (2 réplicas). Si los dos pods
arrancan a la vez (deploy nuevo, reinicio de nodo), dos "alembic upgrade
head" concurrentes contra el mismo Postgres es una carrera real — Alembic
no tiene locking propio para esto.

Se bloquea (pg_advisory_lock, no el "try" que usa el scheduler — acá SÍ
queremos esperar, no saltarnos la migración) con el mismo patrón que ya usa
app/services/scheduler.py para el reentrenamiento. La segunda réplica espera,
adquiere el lock cuando la primera termina, corre `alembic upgrade head` de
nuevo (ya no-op, queda al día) y sigue.

Uso (reemplaza la llamada directa a `alembic upgrade head`):
    python scripts/migrate_with_lock.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

# Distinta de RETRAIN_LOCK_KEY (727311, ver app/services/scheduler.py) —
# cada advisory lock necesita su propia clave para no interferir entre sí.
MIGRATION_LOCK_KEY = 727312


def main() -> None:
    settings = get_settings()
    admin_url = settings.migration_database_url or settings.database_url

    if not admin_url.startswith("postgresql"):
        # SQLite (dev local sin Docker): un solo proceso, no hay con quién competir.
        sys.exit(subprocess.call(["alembic", "upgrade", "head"]))

    engine = create_engine(admin_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        try:
            result = subprocess.call(["alembic", "upgrade", "head"])
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
    sys.exit(result)


if __name__ == "__main__":
    main()
