"""Job programado de reentrenamiento (Semana 7).

Sustituto pragmático de Celery beat + Redis mientras no hay Docker en este
entorno (ver README, "Base de datos local"): un BackgroundScheduler corre en
un hilo propio del mismo proceso uvicorn. La lógica de negocio (comparar F1
contra el champion, promover o no) es la misma que usaría un worker de
Celery — migrar allá en la Semana 8 es cambiar el disparador, no la lógica.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.services.model_admin import trigger_ai4i_retrain

logger = logging.getLogger(__name__)
settings = get_settings()
scheduler = BackgroundScheduler()


def _run_retrain_job() -> None:
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
