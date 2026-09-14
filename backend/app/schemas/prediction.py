from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Debe coincidir con el CheckConstraint("prediction_type IN (...)") de
# app/models/prediction.py. Antes era un str con Field(pattern=...); un
# Literal valida exactamente lo mismo y además da un union real en el
# contrato de tipos generado (frontend/src/lib/api-schema.ts).
PredictionType = Literal["rul_days", "anomaly_score", "failure_probability"]


class PredictionRequest(BaseModel):
    """Dispara inferencia sobre la última lectura conocida del activo (UC1/UC2)."""

    prediction_type: PredictionType


class PredictionOut(BaseModel):
    id: str
    asset_id: str
    predicted_at: datetime
    model_name: str
    model_version: str
    prediction_type: PredictionType
    value: float
    metadata: dict = Field(validation_alias="prediction_metadata")

    model_config = {"from_attributes": True, "populate_by_name": True}
