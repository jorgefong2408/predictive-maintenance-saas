"""Semana 3-4 — Modelo de RUL (Remaining Useful Life) sobre NASA C-MAPSS FD001.

Dos modelos, mismo train/test (los splits oficiales del dataset, no un split
aleatorio: train = motores hasta el fallo, test = motores cortados antes del
fallo con RUL verdadero conocido vía RUL_FD001.txt):
  1. Baseline de regresión lineal sobre las señales crudas — punto de
     comparación obligatorio.
  2. XGBoost — modelo candidato a producción.

Se descartan las columnas constantes en FD001 (sensores que no varían bajo
una única condición operativa) porque no aportan señal y sólo añaden ruido.

Uso:
    uv run python ml/pipelines/train_cmapss_rul.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import mlflow.xgboost
import pandas as pd
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.metrics import regression_metrics  # noqa: E402

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
MLFLOW_DB = Path(__file__).resolve().parents[1] / "mlflow.db"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{MLFLOW_DB}")

NON_FEATURE_COLS = {"unit_number", "cycle", "RUL", "subset"}


def select_features(train: pd.DataFrame) -> list[str]:
    """Descarta columnas constantes en train (no aportan señal en FD001)."""
    candidate_cols = [c for c in train.columns if c not in NON_FEATURE_COLS]
    return [c for c in candidate_cols if train[c].std() > 1e-6]


def main() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("cmapss-rul-fd001")

    train = pd.read_parquet(PROCESSED_DIR / "cmapss_fd001_train.parquet")
    test = pd.read_parquet(PROCESSED_DIR / "cmapss_fd001_test.parquet")

    feature_cols = select_features(train)
    print(f"Features usadas ({len(feature_cols)}): {feature_cols}")

    X_train, y_train = train[feature_cols], train["RUL"]
    X_test, y_test = test[feature_cols], test["RUL"]

    results = {}

    with mlflow.start_run(run_name="baseline_linear_regression"):
        model = LinearRegression()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        metrics = regression_metrics(y_test, y_pred)
        mlflow.log_params({"model": "LinearRegression", "n_features": len(feature_cols)})
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, name="model")
        results["linear_regression"] = metrics

    with mlflow.start_run(run_name="xgboost_regressor") as run:
        model = XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        metrics = regression_metrics(y_test, y_pred)
        mlflow.log_params(
            {"model": "XGBRegressor", "n_estimators": 300, "max_depth": 5, "learning_rate": 0.05}
        )
        mlflow.log_metrics(metrics)
        mlflow.xgboost.log_model(model, name="model")
        results["xgboost"] = metrics
        best_run_id = run.info.run_id

    if results["xgboost"]["rmse"] < results["linear_regression"]["rmse"]:
        mlflow.register_model(f"runs:/{best_run_id}/model", "cmapss-rul-regressor")
        best_name = "xgboost"
    else:
        best_name = "linear_regression"

    print("\n=== Comparación de modelos — C-MAPSS FD001 (RUL, clip=125) ===")
    print(pd.DataFrame(results).T.round(3).to_string())
    print(f"\nMejor modelo por RMSE: {best_name}")


if __name__ == "__main__":
    main()
