from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Claims, get_current_claims, get_tenant_scoped_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    claims: Claims = Depends(get_current_claims),
    db: AsyncSession = Depends(get_tenant_scoped_db),
) -> list[Alert]:
    stmt = select(Alert).where(Alert.tenant_id == claims.tenant_id)
    if active_only:
        stmt = stmt.where(Alert.resolved_at.is_(None))
    result = await db.execute(stmt.order_by(Alert.triggered_at.desc()).offset(offset).limit(limit))
    return list(result.scalars().all())


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(
    alert_id: str, claims: Claims = Depends(get_current_claims), db: AsyncSession = Depends(get_tenant_scoped_db)
) -> Alert:
    alert = (
        await db.execute(select(Alert).where(Alert.id == alert_id, Alert.tenant_id == claims.tenant_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = claims.user_id
    await db.commit()
    await db.refresh(alert)
    return alert
