"""Servicio de inferencia: carga modelos desde el MLflow Model Registry
(trackeados por ml/pipelines/train_ai4i_models.py y train_cmapss_rul.py) y
los aplica sobre las últimas lecturas conocidas de un activo.

Solo `failure_probability` está conectado end-to-end (el activo, sus lecturas
AI4I y el modelo registrado viven en el mismo esquema relacional). `rul_days`
queda pendiente de la Semana 6, cuando C-MAPSS se incorpore también al
esquema producto (por ahora solo existe como dataset de entrenamiento plano,
ver docs/MODEL_RESULTS.md).
"""

from __future__ import annotations

from functools import lru_cache

import mlflow
import mlflow.xgboost
import pandas as pd
from fastapi import HTTPException, status
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.sensor_reading import SensorReading

settings = get_settings()
mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

AI4I_MODEL_NAME = "ai4i-failure-classifier"
AI4I_MODEL_ALIAS = "champion"
AI4I_FALLBACK_VERSION = "1"  # antes de que exista el alias "champion" (bootstrap)

AI4I_SENSOR_FEATURES = [
    "air_temperature",
    "process_temperature",
    "rotational_speed",
    "torque",
    "tool_wear",
]


@lru_cache
def _load_model_version(version: str):
    return mlflow.xgboost.load_model(f"models:/{AI4I_MODEL_NAME}/{version}")


def _current_ai4i_model() -> tuple[object, str]:
    """Resuelve el alias 'champion' a una versión concreta en cada llamada
    (barato: consulta al registry, no descarga el modelo) y solo carga un
    modelo nuevo si la versión resuelta no está ya en caché. Así, cuando
    ml/pipelines/retrain.py mueve el alias, la próxima predicción sirve el
    modelo nuevo sin reiniciar el proceso (UC5: "sin downtime")."""
    client = MlflowClient()
    try:
        version = client.get_model_version_by_alias(AI4I_MODEL_NAME, AI4I_MODEL_ALIAS).version
    except MlflowException:
        version = AI4I_FALLBACK_VERSION
    return _load_model_version(version), version


def _latest_readings_by_sensor(db: Session, asset_id: str) -> dict[str, float]:
    subq = (
        db.query(
            SensorReading.sensor_name,
            func.max(SensorReading.time).label("max_time"),
        )
        .filter(SensorReading.asset_id == asset_id)
        .group_by(SensorReading.sensor_name)
        .subquery()
    )
    rows = (
        db.query(SensorReading)
        .join(
            subq,
            (SensorReading.sensor_name == subq.c.sensor_name) & (SensorReading.time == subq.c.max_time),
        )
        .filter(SensorReading.asset_id == asset_id)
        .all()
    )
    return {row.sensor_name: row.value for row in rows}


def predict_failure_probability(db: Session, asset: Asset) -> tuple[float, str]:
    latest = _latest_readings_by_sensor(db, asset.id)
    missing = [s for s in AI4I_SENSOR_FEATURES if s not in latest]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Faltan lecturas recientes de: {', '.join(missing)}",
        )

    quality_variant = (asset.asset_metadata or {}).get("quality_variant", "H")
    features = {
        **{s: latest[s] for s in AI4I_SENSOR_FEATURES},
        "Type_L": 1.0 if quality_variant == "L" else 0.0,
        "Type_M": 1.0 if quality_variant == "M" else 0.0,
    }
    X = pd.DataFrame([features])[AI4I_SENSOR_FEATURES + ["Type_L", "Type_M"]]

    model, version = _current_ai4i_model()
    probability = float(model.predict_proba(X)[0, 1])
    return probability, version
