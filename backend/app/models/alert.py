from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import GUID, new_uuid


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_alert_severity"),
        # GET /alerts filtra siempre por tenant_id (+ resolved_at IS NULL en
        # el caso default active_only=true) — sin este índice, esa consulta
        # hace sequential scan sobre toda la tabla a medida que crece.
        Index("ix_alerts_tenant_resolved", "tenant_id", "resolved_at"),
        Index("ix_alerts_asset_id", "asset_id"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    severity: Mapped[str] = mapped_column(String, nullable=False)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
