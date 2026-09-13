from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import GUID, new_uuid


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "prediction_type IN ('rul_days', 'anomaly_score', 'failure_probability')",
            name="ck_prediction_type",
        ),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prediction_type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
