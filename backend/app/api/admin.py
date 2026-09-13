import mlflow
from fastapi import APIRouter, Depends, HTTPException, status
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from app.api.deps import Claims, require_role
from app.core.config import get_settings
from app.services.model_admin import trigger_ai4i_retrain

router = APIRouter(prefix="/admin/models", tags=["admin"])

settings = get_settings()
mlflow.set_tracking_uri(settings.mlflow_tracking_uri)


@router.post("/ai4i-failure-classifier/retrain")
def retrain_ai4i_model(claims: Claims = Depends(require_role("admin"))) -> dict:
    """UC5: reentrena y solo promueve el alias 'champion' si el F1 mejora."""
    return trigger_ai4i_retrain()


@router.get("/{model_name}/versions")
def list_model_versions(model_name: str, claims: Claims = Depends(require_role("admin"))) -> list[dict]:
    client = MlflowClient()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except MlflowException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        champion_version = client.get_model_version_by_alias(model_name, "champion").version
    except MlflowException:
        champion_version = None

    result = []
    for mv in sorted(versions, key=lambda v: int(v.version), reverse=True):
        run = client.get_run(mv.run_id)
        result.append(
            {
                "version": mv.version,
                "run_id": mv.run_id,
                "created_at": mv.creation_timestamp,
                "metrics": run.data.metrics,
                "is_champion": mv.version == champion_version,
            }
        )
    return result
