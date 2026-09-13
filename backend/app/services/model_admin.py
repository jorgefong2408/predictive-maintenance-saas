"""Puente hacia ml/pipelines/retrain.py — la lógica de reentrenamiento vive
en ml/ (se comparte con el uso vía CLI/cron), el backend solo la expone
como endpoint autenticado (Semana 7: "endpoint para disparar reentrenamiento
manual y ver historial de versiones de modelo")."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ML_PIPELINES_DIR = PROJECT_ROOT / "ml" / "pipelines"
if str(ML_PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(ML_PIPELINES_DIR))


def trigger_ai4i_retrain() -> dict:
    import retrain  # ml/pipelines/retrain.py

    return retrain.retrain()
