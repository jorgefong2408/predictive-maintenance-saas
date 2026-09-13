from datetime import datetime

from pydantic import BaseModel, Field


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
    status: str
    metadata: dict = Field(validation_alias="asset_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
