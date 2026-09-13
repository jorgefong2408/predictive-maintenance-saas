from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Claims, get_current_claims
from app.core.database import get_db
from app.models.alert import Alert
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    claims: Claims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> list[Alert]:
    query = db.query(Alert).filter(Alert.tenant_id == claims.tenant_id)
    if active_only:
        query = query.filter(Alert.resolved_at.is_(None))
    return query.order_by(Alert.triggered_at.desc()).offset(offset).limit(limit).all()


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: str, claims: Claims = Depends(get_current_claims), db: Session = Depends(get_db)
) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.tenant_id == claims.tenant_id).first()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = claims.user_id
    db.commit()
    db.refresh(alert)
    return alert
