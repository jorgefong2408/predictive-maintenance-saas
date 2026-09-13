"""Semana 3-4 — Modelado sobre AI4I 2020: baseline, detección de anomalías y
clasificación de falla, con tracking de experimentos en MLflow.

Tres modelos, mismo split train/test, comparables entre sí:
  1. Baseline (DummyClassifier, siempre predice la clase mayoritaria) — piso
     de referencia obligatorio antes de creer cualquier métrica "buena".
  2. Isolation Forest (no supervisado) — detecta outliers sin usar la
     etiqueta `Machine failure`; útil para producción cuando aparecen modos
     de falla nuevos no vistos en entrenamiento.
  3. XGBoost (supervisado, con scale_pos_weight por el desbalance ~3.4%) —
     modelo candidato a producción para clasificación de falla.

Uso:
    uv run python ml/pipelines/train_ai4i_models.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.metrics import classification_metrics  # noqa: E402

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "ai4i2020.csv"
MLFLOW_DB = Path(__file__).resolve().parents[1] / "mlflow.db"
# Semana 8: en docker-compose, MLFLOW_TRACKING_URI apunta al servicio mlflow
# real (http://mlflow:5000); sin esa variable (dev local sin Docker, Semanas
# 3-7), cae al sqlite local — mismo código en ambos casos.
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{MLFLOW_DB}")
SENSOR_COLS = {
    "Air temperature [K]": "air_temperature",
    "Process temperature [K]": "process_temperature",
    "Rotational speed [rpm]": "rotational_speed",
    "Torque [Nm]": "torque",
    "Tool wear [min]": "tool_wear",
}
TARGET_COL = "Machine failure"


def load_features() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(RAW_PATH)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns=SENSOR_COLS)
    X = pd.get_dummies(df[list(SENSOR_COLS.values()) + ["Type"]], columns=["Type"], drop_first=True)
    y = df[TARGET_COL]
    return X, y


def run_baseline(X_train, X_test, y_train, y_test) -> dict:
    model = DummyClassifier(strategy="most_frequent")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    return classification_metrics(y_test, y_pred)


def run_isolation_forest(X_train, X_test, y_train, y_test) -> tuple[dict, IsolationForest, StandardScaler]:
    scaler = StandardScaler().fit(X_train)
    contamination = max(y_train.mean(), 0.01)

    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=200)
    model.fit(scaler.transform(X_train))

    raw_pred = model.predict(scaler.transform(X_test))  # -1 = anomalía, 1 = normal
    y_pred = (raw_pred == -1).astype(int)
    anomaly_score = -model.decision_function(scaler.transform(X_test))  # mayor = más anómalo

    metrics = classification_metrics(y_test, y_pred, y_score=anomaly_score)
    metrics["contamination"] = contamination
    return metrics, model, scaler


def run_xgboost(X_train, X_test, y_train, y_test) -> tuple[dict, XGBClassifier]:
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_score = model.predict_proba(X_test)[:, 1]
    metrics = classification_metrics(y_test, y_pred, y_score=y_score)
    metrics["scale_pos_weight"] = scale_pos_weight
    return metrics, model


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("ai4i-failure-detection")

    X, y = load_features()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    results = {}

    with mlflow.start_run(run_name="baseline_dummy"):
        metrics = run_baseline(X_train, X_test, y_train, y_test)
        mlflow.log_params({"model": "DummyClassifier", "strategy": "most_frequent"})
        mlflow.log_metrics(metrics)
        results["baseline"] = metrics

    with mlflow.start_run(run_name="isolation_forest"):
        metrics, if_model, scaler = run_isolation_forest(X_train, X_test, y_train, y_test)
        mlflow.log_params({"model": "IsolationForest", "n_estimators": 200})
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.sklearn.log_model(if_model, name="model")
        results["isolation_forest"] = metrics

    with mlflow.start_run(run_name="xgboost_classifier") as run:
        metrics, xgb_model = run_xgboost(X_train, X_test, y_train, y_test)
        mlflow.log_params(
            {"model": "XGBClassifier", "n_estimators": 300, "max_depth": 4, "learning_rate": 0.05}
        )
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.xgboost.log_model(xgb_model, name="model")
        results["xgboost"] = metrics
        best_run_id = run.info.run_id

    # Registrar el mejor modelo (mayor F1) en el Model Registry.
    best_name = max(results, key=lambda k: results[k].get("f1", 0))
    if best_name == "xgboost":
        mlflow.register_model(f"runs:/{best_run_id}/model", "ai4i-failure-classifier")

    print("\n=== Comparación de modelos — AI4I 2020 (clasificación de falla) ===")
    summary = pd.DataFrame(results).T
    print(summary.round(4).to_string())
    print(f"\nMejor modelo por F1: {best_name}")


if __name__ == "__main__":
    main()
