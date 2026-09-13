from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import Claims, get_current_claims
from app.core.database import get_db
from app.models.alert import Alert
from app.models.asset import Asset
from app.models.prediction import Prediction
from app.schemas.alert import AlertOut
from app.schemas.prediction import PredictionOut, PredictionRequest
from app.services import inference
from app.services.ws_manager import manager

router = APIRouter(prefix="/assets/{asset_id}/predictions", tags=["predictions"])

MODEL_NAME_BY_TYPE = {"failure_probability": "ai4i-failure-classifier"}

# UC1: una predicción de riesgo alto dispara una alerta sin intervención manual.
# Semana 6 conecta esto a un push por WebSocket hacia el dashboard.
FAILURE_PROBABILITY_WARNING = 0.5
FAILURE_PROBABILITY_CRITICAL = 0.8


def _maybe_create_alert(db: Session, asset: Asset, tenant_id: str, prediction: Prediction) -> None:
    if prediction.prediction_type != "failure_probability" or prediction.value < FAILURE_PROBABILITY_WARNING:
        return
    severity = "critical" if prediction.value >= FAILURE_PROBABILITY_CRITICAL else "warning"
    message = (
        f"Probabilidad de falla {prediction.value:.0%} "
        f"(modelo {prediction.model_name} v{prediction.model_version})"
    )
    alert = Alert(
        tenant_id=tenant_id,
        asset_id=asset.id,
        severity=severity,
        alert_type="failure_probability_high",
        message=message,
    )
    db.add(alert)
    asset.status = severity
    db.commit()
    db.refresh(alert)

    manager.broadcast_threadsafe(
        tenant_id, {"type": "alert", "alert": AlertOut.model_validate(alert).model_dump(mode="json")}
    )


def _get_owned_asset(asset_id: str, tenant_id: str, db: Session) -> Asset:
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.tenant_id == tenant_id).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset


@router.post("", response_model=PredictionOut, status_code=status.HTTP_201_CREATED)
def create_prediction(
    asset_id: str,
    payload: PredictionRequest,
    claims: Claims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> Prediction:
    asset = _get_owned_asset(asset_id, claims.tenant_id, db)

    if payload.prediction_type != "failure_probability":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"'{payload.prediction_type}' aún no está conectado end-to-end "
                "(pendiente de incorporar C-MAPSS al esquema producto, Semana 6)."
            ),
        )

    value, model_version = inference.predict_failure_probability(db, asset)
    prediction = Prediction(
        tenant_id=claims.tenant_id,
        asset_id=asset.id,
        model_name=MODEL_NAME_BY_TYPE[payload.prediction_type],
        model_version=model_version,
        prediction_type=payload.prediction_type,
        value=value,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    _maybe_create_alert(db, asset, claims.tenant_id, prediction)
    return prediction


@router.get("", response_model=list[PredictionOut])
def list_predictions(
    asset_id: str, claims: Claims = Depends(get_current_claims), db: Session = Depends(get_db)
) -> list[Prediction]:
    _get_owned_asset(asset_id, claims.tenant_id, db)
    return (
        db.query(Prediction)
        .filter(Prediction.asset_id == asset_id)
        .order_by(Prediction.predicted_at.desc())
        .all()
    )
