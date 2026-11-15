from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
)


http_url_adapter = TypeAdapter(HttpUrl)


class MonitorCreate(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=100,
        description="Monitor name"
    )


    url: str

    webhook_url: Optional[HttpUrl] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:

        value = value.strip()

        if not value:
            raise ValueError("Monitor name cannot be empty")

        return value

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: str) -> str:

        if not isinstance(value, str):
            raise ValueError("URL must be a string")

        value = value.strip()

        if not value:
            raise ValueError("URL cannot be empty")

        
        if any(char.isspace() for char in value):
            raise ValueError("URL cannot contain whitespace")

        if "://" not in value:
            value = "https://" + value

        try:

            parsed_url = http_url_adapter.validate_python(value)

        except Exception:
            raise ValueError("Please enter a valid HTTP or HTTPS URL")

        
        if parsed_url.scheme not in ("http", "https"):
            raise ValueError("Only HTTP and HTTPS URLs are supported")

        # Adres musi miec hosta
        if not parsed_url.host:
            raise ValueError("URL must contain a valid hostname")

        # Nie moze byc haslo ani nazwa jakas
        if parsed_url.username or parsed_url.password:
            raise ValueError("URLs containing credentials are not allowed")

        return str(parsed_url)

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(
        cls,
        value: Optional[HttpUrl]
    ) -> Optional[HttpUrl]:

        if value is not None:

            if value.scheme not in ("http", "https"):
                raise ValueError(
                    "Webhook URL must use HTTP or HTTPS"
                )

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
