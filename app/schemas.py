from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl

class MonitorCreate(BaseModel):
    name: str
    url: HttpUrl
    webhook_url: Optional[HttpUrl] = None

class CheckLogOut(BaseModel):
    id: int
    status_code: Optional[int]
    response_time_ms: Optional[float]
    is_up: bool
    error_message: Optional[str]
    checked_at: datetime

    class Config:
        from_attributes = True

class MonitorOut(BaseModel):
    id: int
    name: str
    url: str
    webhook_url: Optional[str]
    is_up: bool
    last_checked: Optional[datetime]

    class Config:
        from_attributes = True