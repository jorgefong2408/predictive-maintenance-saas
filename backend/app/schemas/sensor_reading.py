from datetime import datetime

from pydantic import BaseModel


class SensorReadingIn(BaseModel):
    time: datetime
    asset_id: str
    sensor_name: str
    value: float
    unit: str | None = None


class SensorReadingOut(BaseModel):
    time: datetime
    asset_id: str
    sensor_name: str
    value: float
    unit: str | None

    model_config = {"from_attributes": True}
