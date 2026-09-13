from datetime import datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import GUID


class SensorReading(Base):
    """Formato largo (time, asset_id, sensor_name) -> value.

    En Postgres, Semana 8 convierte esta tabla en hypertable de TimescaleDB
    (ver infra/sql/001_schema.sql); en SQLite (dev local) es una tabla normal.
    """

    __tablename__ = "sensor_readings"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    asset_id: Mapped[str] = mapped_column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    sensor_name: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
