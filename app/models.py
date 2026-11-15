import time
import logging

from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models import Monitor, CheckLog



REQUEST_TIMEOUT = 10.0
WEBHOOK_TIMEOUT = 5.0

logger = logging.getLogger("uptmon.checker")



async def send_webhook_alert(
    webhook_url: str,
    monitor: Monitor,
    is_up: bool,
    error: Optional[str] = None
):
    if not webhook_url:
        return

    status_text = (
        "SERVICE RESTORED"
        if is_up
        else "SERVICE DOWN"
    )

    message = (
        f"**{status_text}**\n"
        f"**Service:** {monitor.name}\n"
        f"**URL:** {monitor.url}"
    )

    if error and not is_up:
        message += f"\n**Reason:** `{error[:300]}`"

    payload = {
        "content": message,
        "text": message
    }

    try:
        async with httpx.AsyncClient(
            timeout=WEBHOOK_TIMEOUT
        ) as client:

            response = await client.post(
                webhook_url,
                json=payload
            )

            response.raise_for_status()

        logger.info(
            "Webhook notification sent for monitor %s",
            monitor.id
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Webhook returned HTTP %s for monitor %s",
            exc.response.status_code,
            monitor.id
        )

    except httpx.RequestError as exc:
        logger.error(
            "Webhook connection failed for monitor %s: %s",
            monitor.id,
            type(exc).__name__
        )

    except Exception:
        logger.exception(
            "Unexpected webhook error for monitor %s",
            monitor.id
        )



async def check_single_monitor(
    db: Session,
    monitor: Monitor
):

    start_time = time.perf_counter()

    status_code = None
    is_up = False
    error_msg = None


    previous_status = monitor.is_up


    webhook_url = monitor.webhook_url
    monitor_id = monitor.id

    try:

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True
        ) as client:

            response = await client.get(monitor.url)

            status_code = response.status_code

            is_up = (
                200 <= status_code < 400
            )

            if not is_up:
                error_msg = f"HTTP {status_code}"

    except httpx.TimeoutException:
        error_msg = "Request timeout"

    except httpx.ConnectError:
        error_msg = "Connection failed"

    except httpx.TooManyRedirects:
        error_msg = "Too many redirects"

    except httpx.RequestError as exc:
        error_msg = (
            f"Request error: {type(exc).__name__}"
        )

    except Exception as exc:
        error_msg = (
            f"Unexpected error: {type(exc).__name__}"
        )

        logger.exception(
            "Unexpected monitoring error for monitor %s",
            monitor_id
        )


    elapsed_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2
    )

    now = datetime.now(timezone.utc)


    log = CheckLog(
        monitor_id=monitor_id,
        status_code=status_code,
        response_time_ms=elapsed_ms,
        is_up=is_up,
        error_message=error_msg,
        checked_at=now
    )

    try:

        db.add(log)

        monitor.is_up = is_up
        monitor.last_checked = now

        db.commit()

    except Exception:

        db.rollback()

        logger.exception(
            "Database error while saving monitor %s",
            monitor_id
        )

        raise


    status_changed = (
        previous_status is not None
        and previous_status != is_up
    )

    if status_changed and webhook_url:

        await send_webhook_alert(
            webhook_url=webhook_url,
            monitor=monitor,
            is_up=is_up,
            error=error_msg
        )


    logger.info(
        "Monitor %s | Status: %s | HTTP: %s | Response: %.2f ms",
        monitor_id,
        "ONLINE" if is_up else "OFFLINE",
        status_code or "N/A",
        elapsed_ms
    )

    return {
        "monitor_id": monitor_id,
        "is_up": is_up,
        "status_code": status_code,
        "response_time_ms": elapsed_ms,
        "error": error_msg,
        "checked_at": now
    }
