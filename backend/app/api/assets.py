from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import Claims, get_current_claims
from app.core.database import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetOut

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
def list_assets(claims: Claims = Depends(get_current_claims), db: Session = Depends(get_db)) -> list[Asset]:
    """UC3/UC4: solo devuelve activos del tenant del token, nunca de otro."""
    return (
        db.query(Asset)
        .filter(Asset.tenant_id == claims.tenant_id)
        .order_by(Asset.status.desc(), Asset.name)
        .all()
    )


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate, claims: Claims = Depends(get_current_claims), db: Session = Depends(get_db)
) -> Asset:
    asset = Asset(
        tenant_id=claims.tenant_id,
        name=payload.name,
        asset_type=payload.asset_type,
        external_ref=payload.external_ref,
        asset_metadata=payload.metadata,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, claims: Claims = Depends(get_current_claims), db: Session = Depends(get_db)) -> Asset:
    asset = (
        db.query(Asset).filter(Asset.id == asset_id, Asset.tenant_id == claims.tenant_id).first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activo no encontrado")
    return asset
