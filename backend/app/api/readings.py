from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Claims, get_current_claims, get_tenant_scoped_db
from app.models.asset import Asset
from app.models.sensor_reading import SensorReading
from app.models.types import to_naive_utc
from app.schemas.sensor_reading import SensorReadingIn, SensorReadingOut

router = APIRouter(prefix="/assets/{asset_id}/readings", tags=["readings"])


async def _get_owned_asset(asset_id: str, tenant_id: str, db: AsyncSession) -> Asset:
    asset = (
        await db.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset


@router.post("", status_code=status.HTTP_201_CREATED)
async def ingest_reading(
    asset_id: str,
    payload: SensorReadingIn,
    claims: Claims = Depends(get_current_claims),
    db: AsyncSession = Depends(get_tenant_scoped_db),
) -> dict:
    """Punto de entrada del simulador (ml/pipelines/simulate_realtime.py) y de
    cualquier fuente de datos real en el futuro."""
    await _get_owned_asset(asset_id, claims.tenant_id, db)
    reading = SensorReading(
        time=to_naive_utc(payload.time),
        asset_id=asset_id,
        tenant_id=claims.tenant_id,
        sensor_name=payload.sensor_name,
        value=payload.value,
        unit=payload.unit,
    )
    await db.merge(reading)  # idempotente: mismo (time, asset_id, sensor_name) sobrescribe
    await db.commit()
    return {"status": "ok"}


@router.get("", response_model=list[SensorReadingOut])
async def list_readings(
    asset_id: str,
    sensor_name: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=500, le=5000),
    claims: Claims = Depends(get_current_claims),
    db: AsyncSession = Depends(get_tenant_scoped_db),
) -> list[SensorReading]:
    await _get_owned_asset(asset_id, claims.tenant_id, db)
    stmt = select(SensorReading).where(SensorReading.asset_id == asset_id)
    if sensor_name:
        stmt = stmt.where(SensorReading.sensor_name == sensor_name)
    if since:
        stmt = stmt.where(SensorReading.time >= to_naive_utc(since))
    result = await db.execute(stmt.order_by(SensorReading.time.desc()).limit(limit))
    return list(result.scalars().all())
