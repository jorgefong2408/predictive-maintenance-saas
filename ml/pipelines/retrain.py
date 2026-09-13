"""Semana 7 — Reentrenamiento con promoción condicional (patrón "champion").

Reentrena el clasificador de falla de AI4I, registra la corrida como una
nueva versión en el Model Registry, y solo mueve el alias `champion` (el que
sirve el backend, ver app/services/inference.py) a la versión nueva si su F1
supera al del champion actual. Así, un reentrenamiento nunca degrada
silenciosamente el modelo en producción.

Limitación explícita de esta fase: como el dataset es estático (AI4I 2020),
"reentrenar" repite el mismo proceso de entrenamiento sobre los mismos datos
— no hay todavía un flujo real de acumulación de lecturas nuevas en
`sensor_readings` para reentrenar sobre datos frescos. Eso llega junto con
un pipeline de feature extraction desde la base (fuera de alcance de esta
fase); aquí se deja lista la mecánica de versionado/promoción, que es la
que no cambia cuando eso se conecte.

Uso:
    uv run python ml/pipelines/retrain.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import mlflow
import mlflow.xgboost
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_ai4i_models import MLFLOW_TRACKING_URI, load_features, run_xgboost  # noqa: E402

MODEL_NAME = "ai4i-failure-classifier"
ALIAS = "champion"


def _current_champion_f1(client: MlflowClient) -> tuple[float, str | None]:
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, ALIAS)
    except MlflowException:
        return float("-inf"), None
    run = client.get_run(mv.run_id)
    return run.data.metrics.get("f1", float("-inf")), mv.version


def retrain() -> dict:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("ai4i-failure-detection")
    client = MlflowClient()

    champion_f1, champion_version = _current_champion_f1(client)

    X, y = load_features()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    with mlflow.start_run(run_name="retrain_xgboost") as run:
        metrics, model = run_xgboost(X_train, X_test, y_train, y_test)
        mlflow.log_params({"model": "XGBClassifier", "trigger": "retrain"})
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        mlflow.xgboost.log_model(model, name="model")
        model_uri = f"runs:/{run.info.run_id}/model"

    new_version = mlflow.register_model(model_uri, MODEL_NAME).version
    promoted = metrics["f1"] > champion_f1
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, ALIAS, new_version)

    return {
        "new_version": new_version,
        "new_f1": metrics["f1"],
        "previous_champion_version": champion_version,
        "previous_champion_f1": None if champion_f1 == float("-inf") else champion_f1,
        "promoted": promoted,
    }


def main() -> None:
    result = retrain()
    verdict = "PROMOVIDO a champion" if result["promoted"] else "descartado (no supera al champion actual)"
    print(f"Nueva versión: {result['new_version']} (F1={result['new_f1']:.4f}) — {verdict}")
    if result["previous_champion_version"]:
        print(f"Champion previo: v{result['previous_champion_version']} (F1={result['previous_champion_f1']:.4f})")


if __name__ == "__main__":
    main()
