from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import GUID, new_uuid

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'warning', 'critical')", name="ck_asset_status"),
        UniqueConstraint("tenant_id", "external_ref", name="uq_asset_tenant_external_ref"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    asset_type: Mapped[str] = mapped_column(String, nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ok")
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    installed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    tenant: Mapped["Tenant"] = relationship(back_populates="assets")
