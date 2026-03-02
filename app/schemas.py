from datetime import datetime
from pydantic import BaseModel


class ServiceCheckOut(BaseModel):
    id: int
    service_name: str
    url: str
    expected_version: str | None = None
    observed_version: str | None = None
    status: str
    status_code: int | None = None
    latency_ms: float | None = None
    version_drift: bool
    error_message: str | None = None
    checked_at: datetime

    class Config:
        from_attributes = True