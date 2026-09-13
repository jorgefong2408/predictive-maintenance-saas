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

import time
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


ALIAS_CACHE_TTL_SECONDS = 30
_alias_cache: dict[str, tuple[str, float]] = {}


@lru_cache
def _load_model_version(version: str):
    model = mlflow.xgboost.load_model(f"models:/{AI4I_MODEL_NAME}/{version}")
    # XGBoost por defecto usa todos los cores por predicción (n_jobs=-1); para
    # una fila a la vez eso no acelera nada y bajo concurrencia real cada
    # request compite por todos los cores. Buena práctica de todos modos,
    # aunque en la prueba de carga (load-testing/RESULTS.md) NO resultó ser
    # la causa de la cola p99 — esa sigue sin explicación confirmada.
    model.set_params(n_jobs=1)
    return model


def _resolve_champion_version() -> str:
    """Resolver el alias contra MLflow es una llamada de red — hacerlo en
    cada predicción resultó ser el cuello de botella real bajo carga (Semana
    9: p99 de ~7s con Locust, ver load-testing/RESULTS.md). Se cachea la
    versión resuelta por ALIAS_CACHE_TTL_SECONDS: sigue habiendo recarga sin
    downtime tras un reentrenamiento (UC5), solo que con hasta 30s de
    staleness en vez de resolverlo en cada request."""
    cached = _alias_cache.get(AI4I_MODEL_ALIAS)
    now = time.monotonic()
    if cached is not None and now - cached[1] < ALIAS_CACHE_TTL_SECONDS:
        return cached[0]

    client = MlflowClient()
    try:
        version = client.get_model_version_by_alias(AI4I_MODEL_NAME, AI4I_MODEL_ALIAS).version
    except MlflowException:
        version = AI4I_FALLBACK_VERSION
    _alias_cache[AI4I_MODEL_ALIAS] = (version, now)
    return version


def _current_ai4i_model() -> tuple[object, str]:
    version = _resolve_champion_version()
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
