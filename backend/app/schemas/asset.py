from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Debe coincidir con el CheckConstraint("status IN (...)") de app/models/asset.py
# -- Literal (no str) para que el contrato de tipos generado para el frontend
# (frontend/src/lib/api-schema.ts, ver "npm run codegen") sea un union real,
# no un string abierto.
AssetStatus = Literal["ok", "warning", "critical"]


class AssetCreate(BaseModel):
    name: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    external_ref: str | None = None
    metadata: dict = Field(default_factory=dict)


class AssetOut(BaseModel):
    id: str
    name: str
    asset_type: str
    external_ref: str | None
    status: AssetStatus
    metadata: dict = Field(validation_alias="asset_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
