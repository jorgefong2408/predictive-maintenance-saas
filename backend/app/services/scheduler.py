"""Job programado de reentrenamiento (Semana 7).

Sustituto pragmático de Celery beat + Redis mientras no hay Docker en este
entorno (ver README, "Base de datos local"): un BackgroundScheduler corre en
un hilo propio del mismo proceso uvicorn. La lógica de negocio (comparar F1
contra el champion, promover o no) es la misma que usaría un worker de
Celery — migrar allá en la Semana 8 es cambiar el disparador, no la lógica.

Coordinación entre réplicas: `infra/k8s/04-backend.yaml` corre 2 réplicas del
backend, y cada una levanta su propio scheduler — sin coordinación, las dos
reentrenarían por separado en cada tick, duplicando trabajo (y, en el peor
caso, generando dos "mejores" versiones basadas en el mismo dataset). Se usa
un advisory lock de Postgres (`pg_try_advisory_lock`) para que solo una
réplica ejecute el job en cada tick; las demás lo detectan y lo saltan. No
requiere infraestructura nueva (Postgres ya está en el stack) y es exactamente
para esto que existen los advisory locks: coordinación efímera entre procesos
sin una tabla dedicada.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.services.model_admin import trigger_ai4i_retrain

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = BackgroundScheduler()

# Clave arbitraria pero fija — todas las réplicas deben usar la misma para
# competir por el mismo lock. Un int64 cualquiera sirve.
RETRAIN_LOCK_KEY = 727311


def _run_retrain_job() -> None:
    if engine.dialect.name != "postgresql":
        # SQLite (dev local sin Docker): un solo proceso, no hay con quién competir.
        _do_retrain()
        return

    with engine.connect() as conn:
        acquired = conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": RETRAIN_LOCK_KEY}).scalar()
        if not acquired:
            logger.info("Otra réplica ya tiene el lock de reentrenamiento; se salta este tick")
            return
        try:
            _do_retrain()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": RETRAIN_LOCK_KEY})


def _do_retrain() -> None:
    try:
        result = trigger_ai4i_retrain()
        logger.info("Reentrenamiento programado: %s", result)
    except Exception:
        logger.exception("Falló el job programado de reentrenamiento")


def start() -> None:
    if settings.enable_scheduler and not scheduler.running:
        scheduler.add_job(
            _run_retrain_job,
            "interval",
            hours=settings.retrain_interval_hours,
            id="ai4i_retrain",
            replace_existing=True,
        )
        scheduler.start()


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
