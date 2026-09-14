from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import GUID, new_uuid, utc_now_naive


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "prediction_type IN ('rul_days', 'anomaly_score', 'failure_probability')",
            name="ck_prediction_type",
        ),
        # GET /assets/{id}/predictions filtra por asset_id y ordena por
        # predicted_at desc — índice compuesto cubre ambas partes de la query.
        Index("ix_predictions_asset_predicted_at", "asset_id", "predicted_at"),
    )

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(GUID(), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(default=utc_now_naive)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    prediction_type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
