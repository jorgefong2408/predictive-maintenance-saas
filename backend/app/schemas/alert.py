from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Debe coincidir con el CheckConstraint("severity IN (...)") de app/models/alert.py.
AlertSeverity = Literal["info", "warning", "critical"]


class AlertOut(BaseModel):
    id: str
    asset_id: str
    triggered_at: datetime
    severity: AlertSeverity
    alert_type: str
    message: str
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
