from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import GUID, new_uuid, utc_now_naive

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.user import User


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String, nullable=False, default="free")
    created_at: Mapped[datetime] = mapped_column(default=utc_now_naive)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    assets: Mapped[list["Asset"]] = relationship(back_populates="tenant")
