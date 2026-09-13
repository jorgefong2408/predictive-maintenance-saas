from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Claims, get_current_claims
from app.core.database import get_db
from app.models.asset import Asset
from app.models.sensor_reading import SensorReading
from app.schemas.sensor_reading import SensorReadingIn, SensorReadingOut

router = APIRouter(prefix="/assets/{asset_id}/readings", tags=["readings"])


def _get_owned_asset(asset_id: str, tenant_id: str, db: Session) -> Asset:
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.tenant_id == tenant_id).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset


@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_reading(
    asset_id: str,
    payload: SensorReadingIn,
    claims: Claims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> dict:
    """Punto de entrada del simulador (ml/pipelines/simulate_realtime.py) y de
    cualquier fuente de datos real en el futuro."""
    _get_owned_asset(asset_id, claims.tenant_id, db)
    reading = SensorReading(
        time=payload.time,
        asset_id=asset_id,
        tenant_id=claims.tenant_id,
        sensor_name=payload.sensor_name,
        value=payload.value,
        unit=payload.unit,
    )
    db.merge(reading)  # idempotente: mismo (time, asset_id, sensor_name) sobrescribe
    db.commit()
    return {"status": "ok"}


@router.get("", response_model=list[SensorReadingOut])
def list_readings(
    asset_id: str,
    sensor_name: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
    claims: Claims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> list[SensorReading]:
    _get_owned_asset(asset_id, claims.tenant_id, db)
    query = db.query(SensorReading).filter(SensorReading.asset_id == asset_id)
    if sensor_name:
        query = query.filter(SensorReading.sensor_name == sensor_name)
    if since:
        query = query.filter(SensorReading.time >= since)
    return query.order_by(SensorReading.time.desc()).limit(limit).all()
