import time
from datetime import datetime, timezone
import httpx
from sqlalchemy.orm import Session
from models import Monitor, CheckLog

async def send_webhook_alert(webhook_url: str, monitor: Monitor, is_up: bool, error: str = None):
    if not webhook_url:
        return
    status_text = "WRÓCIŁA DO ŻYCIA" if is_up else "AWARIA (STRONA NIE DZIAŁA)"
    message = f"**{status_text}**\n**Serwis:** {monitor.name}\n**URL:** {monitor.url}"
    if error and not is_up:
        message += f"\n**Powód:** `{error}`"
    payload = {"content": message, "text": message}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception as e:
        print(f"[Błąd Webhooka]: {e}")

async def check_single_monitor(db: Session, monitor: Monitor):
    start_time = time.perf_counter()
    status_code = None
    is_up = False
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(monitor.url)
            status_code = response.status_code
            is_up = 200 <= status_code < 400
            if not is_up:
                error_msg = f"HTTP {status_code}"
    except httpx.RequestError as exc:
        error_msg = f"Błąd połączenia: {type(exc).__name__}"
    except Exception as exc:
        error_msg = str(exc)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    now = datetime.now(timezone.utc)

    log = CheckLog(
        monitor_id=monitor.id,
        status_code=status_code,
        response_time_ms=elapsed_ms if is_up else None,
        is_up=is_up,
        error_message=error_msg,
        checked_at=now,
    )
    db.add(log)

    previous_status = monitor.is_up
    monitor.is_up = is_up
    monitor.last_checked = now
    db.commit()

    if previous_status != is_up and monitor.webhook_url:
        await send_webhook_alert(monitor.webhook_url, monitor, is_up, error_msg)