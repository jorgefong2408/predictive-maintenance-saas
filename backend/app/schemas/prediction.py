from datetime import datetime

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Dispara inferencia sobre la última lectura conocida del activo (UC1/UC2)."""

    prediction_type: str = Field(pattern="^(rul_days|anomaly_score|failure_probability)$")


class PredictionOut(BaseModel):
    id: str
    asset_id: str
    predicted_at: datetime
    model_name: str
    model_version: str
    prediction_type: str
    value: float
    metadata: dict = Field(validation_alias="prediction_metadata")

    model_config = {"from_attributes": True, "populate_by_name": True}
