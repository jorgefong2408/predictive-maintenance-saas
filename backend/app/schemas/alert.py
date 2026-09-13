from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: str
    asset_id: str
    triggered_at: datetime
    severity: str
    alert_type: str
    message: str
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
