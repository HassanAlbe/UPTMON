from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class MonitorCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
        description="Monitor name"
    )

    url: HttpUrl

    webhook_url: Optional[HttpUrl] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Monitor name cannot be empty")

        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme not in ("http", "https"):
            raise ValueError("Only HTTP and HTTPS URLs are supported")

        return value

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(
        cls,
        value: Optional[HttpUrl]
    ) -> Optional[HttpUrl]:
        if value is not None and value.scheme not in ("http", "https"):
            raise ValueError("Webhook URL must use HTTP or HTTPS")

        return value


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    webhook_url: Optional[str] = None
    is_up: bool
    last_checked: Optional[datetime] = None


class CheckLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_up: bool
    error_message: Optional[str] = None
    checked_at: datetime


class MonitorStatsOut(BaseModel):
    uptime_percentage: float
    total_checks: int
    successful_checks: int
    failed_checks: int
    average_response_time: Optional[float] = None
    latest_response_time: Optional[float] = None
    is_up: bool
    last_checked: Optional[datetime] = None
