import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import engine, Base, SessionLocal, get_db
from models import Monitor, CheckLog
from schemas import MonitorCreate, MonitorOut
from checker import check_single_monitor


CHECK_INTERVAL_MINUTES = 1
MAX_CONCURRENT_CHECKS = 10

check_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)



async def check_monitor_by_id(monitor_id: int):
    async with check_semaphore:
        db = SessionLocal()

        try:
            monitor = (
                db.query(Monitor)
                .filter(Monitor.id == monitor_id)
                .first()
            )

            if monitor:
                await check_single_monitor(db, monitor)

        except Exception as exc:
            db.rollback()
            print(f"[Monitor {monitor_id}] Error: {exc}")

        finally:
            db.close()


async def run_all_checks():
    db = SessionLocal()

    try:
        monitor_ids = [
            monitor_id
            for (monitor_id,) in db.query(Monitor.id).all()
        ]
    except Exception as exc:
        print(f"[Scheduler] Database error: {exc}")
        return
    finally:
        db.close()

    if not monitor_ids:
        return

    print(f"[Scheduler] Checking {len(monitor_ids)} monitors...")

    await asyncio.gather(
        *(check_monitor_by_id(mid) for mid in monitor_ids)
    )

    print("[Scheduler] Monitoring cycle completed.")



@asynccontextmanager
async def lifespan(app: FastAPI):

    Base.metadata.create_all(bind=engine)

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_all_checks,
        trigger="interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="uptime_monitor",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30
    )

    scheduler.start()
    app.state.scheduler = scheduler

    print("[UPTMON] Scheduler started.")

    yield

    scheduler.shutdown(wait=False)

    print("[UPTMON] Scheduler stopped.")


app = FastAPI(
    title="UPTMON API",
    description="Website uptime monitoring system",
    version="2.0.0",
    lifespan=lifespan
)



@app.post("/api/monitors", response_model=MonitorOut)
async def create_monitor(
    payload: MonitorCreate,
    db: Session = Depends(get_db)
):
    monitor = Monitor(
        name=payload.name,
        url=str(payload.url),
        webhook_url=(
            str(payload.webhook_url)
            if payload.webhook_url else None
        )
    )

    try:
        db.add(monitor)
        db.commit()
        db.refresh(monitor)

        await check_single_monitor(db, monitor)

        db.refresh(monitor)

        return monitor

    except Exception:
        db.rollback()
        raise



@app.get("/api/monitors", response_model=list[MonitorOut])
def list_monitors(db: Session = Depends(get_db)):

    return (
        db.query(Monitor)
        .order_by(Monitor.id.desc())
        .all()
    )


# ==========================================
# DELETE MONITOR
# ==========================================

@app.delete("/api/monitors/{monitor_id}")
def delete_monitor(
    monitor_id: int,
    db: Session = Depends(get_db)
):

    monitor = (
        db.query(Monitor)
        .filter(Monitor.id == monitor_id)
        .first()
    )

    if not monitor:
        raise HTTPException(
            status_code=404,
            detail="Monitor not found"
        )

    try:
        db.delete(monitor)
        db.commit()

        return {"success": True}

    except Exception:
        db.rollback()
        raise



@app.post("/api/monitors/{monitor_id}/check")
async def manual_check(
    monitor_id: int,
    db: Session = Depends(get_db)
):

    monitor = (
        db.query(Monitor)
        .filter(Monitor.id == monitor_id)
        .first()
    )

    if not monitor:
        raise HTTPException(
            status_code=404,
            detail="Monitor not found"
        )

    await check_single_monitor(db, monitor)
    db.refresh(monitor)

    return {
        "success": True,
        "is_up": monitor.is_up,
        "last_checked": monitor.last_checked
    }



@app.get("/api/monitors/{monitor_id}/history")
def monitor_history(
    monitor_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):

    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id
    ).first()

    if not monitor:
        raise HTTPException(
            status_code=404,
            detail="Monitor not found"
        )

    logs = (
        db.query(CheckLog)
        .filter(CheckLog.monitor_id == monitor_id)
        .order_by(CheckLog.checked_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "status_code": log.status_code,
            "response_time_ms": log.response_time_ms,
            "is_up": log.is_up,
            "error_message": log.error_message,
            "checked_at": log.checked_at
        }
        for log in logs
    ]



@app.get("/api/monitors/{monitor_id}/stats")
def monitor_stats(
    monitor_id: int,
    hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db)
):

    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id
    ).first()

    if not monitor:
        raise HTTPException(
            status_code=404,
            detail="Monitor not found"
        )

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    logs = (
        db.query(CheckLog)
        .filter(
            CheckLog.monitor_id == monitor_id,
            CheckLog.checked_at >= since
        )
        .all()
    )

    total = len(logs)
    successful = sum(1 for log in logs if log.is_up)

    uptime = (
        round((successful / total) * 100, 2)
        if total else 0
    )

    response_times = [
        log.response_time_ms
        for log in logs
        if log.response_time_ms is not None
    ]

    average_response = (
        round(sum(response_times) / len(response_times), 2)
        if response_times else None
    )

    latest = (
        db.query(CheckLog)
        .filter(CheckLog.monitor_id == monitor_id)
        .order_by(CheckLog.checked_at.desc())
        .first()
    )

    return {
        "monitor_id": monitor_id,
        "uptime_percentage": uptime,
        "total_checks": total,
        "successful_checks": successful,
        "failed_checks": total - successful,
        "average_response_time": average_response,
        "latest_response_time": (
            latest.response_time_ms if latest else None
        ),
        "is_up": monitor.is_up,
        "last_checked": monitor.last_checked
    }



@app.get("/", response_class=HTMLResponse)
def dashboard():

    return HTMLResponse(content=r"""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#080d18">

<title>UPTMON — Uptime Monitoring</title>

<style>

:root {
    --bg: #080d18;
    --panel: #101827;
    --panel2: #151f30;
    --border: #243147;
    --text: #edf3fc;
    --muted: #8493aa;
    --blue: #38bdf8;
    --green: #22c55e;
    --red: #ef4444;
    --yellow: #f59e0b;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: Inter, system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}

button, input {
    font: inherit;
}

button {
    cursor: pointer;
}

.layout {
    max-width: 1400px;
    margin: auto;
    padding: 30px;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    margin-bottom: 35px;
}

.logo {
    font-size: 25px;
    font-weight: 800;
    letter-spacing: -1px;
}

.logo span {
    color: var(--blue);
}

.subtitle {
    color: var(--muted);
    font-size: 13px;
    margin-top: 5px;
}

.live {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 13px;
    color: var(--green);
    background: #10251e;
    border: 1px solid #205438;
    border-radius: 30px;
    padding: 9px 15px;
}

.dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 10px var(--green);
}

.section-title {
    font-size: 19px;
    margin-bottom: 18px;
}

.stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
    margin-bottom: 35px;
}

.stat {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 22px;
}

.stat-label {
    color: var(--muted);
    font-size: 13px;
}

.stat-value {
    font-size: 29px;
    font-weight: 750;
    margin-top: 12px;
}

.stat-description {
    font-size: 12px;
    color: var(--muted);
    margin-top: 5px;
}

.green { color: var(--green); }
.red { color: var(--red); }
.blue { color: var(--blue); }

.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 13px;
    padding: 22px;
    margin-bottom: 25px;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
    margin-bottom: 20px;
}

.panel-header h2 {
    font-size: 17px;
}

.muted {
    color: var(--muted);
    font-size: 12px;
}

.primary {
    border: 0;
    border-radius: 7px;
    background: #0284c7;
    color: white;
    padding: 10px 16px;
    font-weight: 650;
    transition: .2s;
}

.primary:hover {
    background: #0369a1;
}

.secondary {
    border: 1px solid var(--border);
    background: var(--panel2);
    color: var(--text);
    padding: 9px 13px;
    border-radius: 7px;
}

.danger {
    border: 1px solid #713333;
    background: #321a21;
    color: #f87171;
    padding: 8px 12px;
    border-radius: 7px;
}

.form-grid {
    display: grid;
    grid-template-columns: 1fr 2fr 2fr auto;
    gap: 10px;
}

input {
    width: 100%;
    padding: 12px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: #0b1321;
    color: white;
    outline: none;
    min-width: 0;
}

input:focus {
    border-color: var(--blue);
}

input::placeholder {
    color: #64748b;
}

.monitor-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.monitor {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: 20px;
    padding: 17px;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 10px;
    transition: border .2s;
}

.monitor:hover {
    border-color: #42617f;
}

.monitor-name {
    font-weight: 700;
    margin-bottom: 6px;
}

.monitor-url {
    font-size: 12px;
    color: var(--muted);
    overflow-wrap: anywhere;
}

.status {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 11px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 750;
}

.status.up {
    background: #103522;
    color: #4ade80;
}

.status.down {
    background: #401c25;
    color: #f87171;
}

.status.pending {
    background: #3b2d12;
    color: #fbbf24;
}

.monitor-actions {
    display: flex;
    gap: 7px;
}

.monitor-actions button {
    font-size: 12px;
}

.empty {
    padding: 35px 15px;
    text-align: center;
    color: var(--muted);
    border: 1px dashed var(--border);
    border-radius: 10px;
}

.details {
    display: none;
}

.details.active {
    display: block;
}

.detail-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}

.detail-stat {
    background: var(--panel2);
    border-radius: 8px;
    padding: 15px;
}

.detail-stat strong {
    display: block;
    font-size: 22px;
    margin-top: 7px;
}

.chart-wrap {
    height: 220px;
    position: relative;
}

canvas {
    width: 100%;
    height: 100%;
}

.history {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.history-item {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 11px;
    border-radius: 7px;
    background: var(--panel2);
    font-size: 12px;
}

footer {
    color: var(--muted);
    text-align: center;
    padding: 25px;
    font-size: 12px;
}

.toast {
    position: fixed;
    right: 25px;
    bottom: 25px;
    padding: 14px 20px;
    background: #17263a;
    border: 1px solid var(--border);
    border-radius: 9px;
    display: none;
    z-index: 10;
    max-width: calc(100vw - 50px);
}

.toast.show {
    display: block;
}

@media(max-width: 850px) {
    .stats {
        grid-template-columns: repeat(2, 1fr);
    }

    .form-grid {
        grid-template-columns: 1fr 1fr;
    }

    .form-grid button {
        grid-column: span 2;
    }
}

@media(max-width: 600px) {
    .layout {
        padding: 17px;
    }

    header {
        align-items: flex-start;
    }

    .stats {
        gap: 9px;
    }

    .stat {
        padding: 15px;
    }

    .stat-value {
        font-size: 23px;
    }

    .monitor {
        grid-template-columns: 1fr;
        gap: 12px;
    }

    .monitor-actions {
        flex-wrap: wrap;
    }

    .form-grid {
        grid-template-columns: 1fr;
    }

    .form-grid button {
        grid-column: auto;
    }

    .detail-stats {
        grid-template-columns: 1fr;
    }

    .panel {
        padding: 15px;
    }
}

</style>
</head>

<body>

<div class="layout">

<header>
    <div>
        <div class="logo">UPT<span>MON</span></div>
        <div class="subtitle">Website uptime monitoring</div>
    </div>

    <div class="live">
        <span class="dot"></span>
        Monitoring active
    </div>
</header>


<section>
    <h2 class="section-title">Overview</h2>

    <div class="stats">

        <div class="stat">
            <div class="stat-label">Total monitors</div>
            <div class="stat-value" id="total">0</div>
            <div class="stat-description">Configured services</div>
        </div>

        <div class="stat">
            <div class="stat-label">Online</div>
            <div class="stat-value green" id="online">0</div>
            <div class="stat-description">Currently available</div>
        </div>

        <div class="stat">
            <div class="stat-label">Offline</div>
            <div class="stat-value red" id="offline">0</div>
            <div class="stat-description">Currently unavailable</div>
        </div>

        <div class="stat">
            <div class="stat-label">Average response</div>
            <div class="stat-value blue" id="average">--</div>
            <div class="stat-description">Latest response times</div>
        </div>

    </div>
</section>


<section class="panel">

    <div class="panel-header">
        <h2>Add new monitor</h2>
        <span class="muted">HTTP monitoring</span>
    </div>

    <form id="addForm">

        <div class="form-grid">

            <input
                id="name"
                type="text"
                placeholder="Monitor name"
                maxlength="100"
                required
            >

            <input
                id="url"
                type="url"
                placeholder="https://example.com"
                required
            >

            <input
                id="webhook"
                type="url"
                placeholder="Discord webhook (optional)"
            >

            <button class="primary" type="submit" id="addButton">
                + Add monitor
            </button>

        </div>

    </form>

</section>


<section class="panel">

    <div class="panel-header">
        <div>
            <h2>Monitored services</h2>
            <div class="muted">Live monitoring overview</div>
        </div>

        <button class="secondary" onclick="loadMonitors()">
            Refresh
        </button>
    </div>

    <div class="monitor-list" id="monitorList">
        <div class="empty">Loading monitors...</div>
    </div>

</section>


<section class="panel details" id="details">

    <div class="panel-header">
        <div>
            <h2 id="detailName">Monitor details</h2>
            <div class="muted" id="detailUrl"></div>
        </div>

        <button class="secondary" onclick="closeDetails()">
            Close
        </button>
    </div>

    <div class="detail-stats">

        <div class="detail-stat">
            <span class="muted">Uptime (24h)</span>
            <strong class="green" id="detailUptime">--</strong>
        </div>

        <div class="detail-stat">
            <span class="muted">Average response</span>
            <strong class="blue" id="detailAverage">--</strong>
        </div>

        <div class="detail-stat">
            <span class="muted">Total checks</span>
            <strong id="detailChecks">--</strong>
        </div>

    </div>

    <h3 style="font-size:14px;margin-bottom:15px">
        Response time history
    </h3>

    <div class="chart-wrap">
        <canvas id="responseChart"></canvas>
    </div>

    <h3 style="font-size:14px;margin:20px 0 12px">
        Recent checks
    </h3>

    <div class="history" id="historyList"></div>

</section>


<footer>
    UPTMON · Website Monitoring System
    <br>
    <span id="lastUpdate">Waiting for data...</span>
</footer>

</div>

<div class="toast" id="toast"></div>


<script>

const API = "/api";
let currentMonitors = [];
let refreshTimer = null;


function showToast(message) {
    const toast = document.getElementById("toast");

    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}


async function apiFetch(url, options = {}) {

    const response = await fetch(url, options);

    if (!response.ok) {
        let message = "Request failed";

        try {
            const data = await response.json();
            message = data.detail || message;
        } catch {}

        throw new Error(message);
    }

    return response.json();
}


function createElement(tag, className, text) {

    const element = document.createElement(tag);

    if (className) {
        element.className = className;
    }

    if (text !== undefined) {
        element.textContent = text;
    }

    return element;
}


async function loadMonitors() {

    const list = document.getElementById("monitorList");

    try {

        const data = await apiFetch(`${API}/monitors`);

        currentMonitors = data;

        document.getElementById("total").textContent = data.length;

        const online = data.filter(m => m.is_up === true).length;
        const offline = data.filter(m => m.is_up === false).length;

        document.getElementById("online").textContent = online;
        document.getElementById("offline").textContent = offline;

        if (!data.length) {

            list.replaceChildren(
                createElement("div", "empty", "No monitors yet. Add your first website above.")
            );

            document.getElementById("average").textContent = "--";
            document.getElementById("lastUpdate").textContent = "Updated just now";

            return;
        }

        const cards = await Promise.all(
            data.map(async monitor => {

                try {
                    const stats = await apiFetch(
                        `${API}/monitors/${monitor.id}/stats`
                    );

                    return { monitor, stats };

                } catch {
                    return { monitor, stats: null };
                }
            })
        );

        let responseTotal = 0;
        let responseCount = 0;

        list.replaceChildren();

        for (const { monitor, stats } of cards) {

            const card = createElement("div", "monitor");

            const info = createElement("div");
            const name = createElement("div", "monitor-name", monitor.name);
            const url = createElement("div", "monitor-url", monitor.url);

            info.append(name, url);

            const status = createElement(
                "span",
                "status " + (
                    monitor.is_up === true ? "up" :
                    monitor.is_up === false ? "down" : "pending"
                ),
                monitor.is_up === true ? "ONLINE" :
                monitor.is_up === false ? "OFFLINE" : "UNKNOWN"
            );

            const metric = stats?.latest_response_time;

            const metricBox = createElement(
                "div",
                "muted",
                metric !== null && metric !== undefined
                    ? `${metric} ms`
                    : "-- ms"
            );

            if (metric !== null && metric !== undefined) {
                responseTotal += metric;
                responseCount++;
            }

            const statusColumn = createElement("div");
            statusColumn.append(status, metricBox);

            const actions = createElement("div", "monitor-actions");

            const detailsButton = createElement("button", "secondary", "Details");

            detailsButton.addEventListener("click", () => {
                showDetails(monitor);
            });

            const checkButton = createElement("button", "secondary", "Check");

            checkButton.addEventListener("click", () => {
                runManualCheck(monitor.id, checkButton);
            });

            const deleteButton = createElement("button", "danger", "Delete");

            deleteButton.addEventListener("click", () => {
                deleteMonitor(monitor.id);
            });

            actions.append(detailsButton, checkButton, deleteButton);

            card.append(info, statusColumn, actions);
            list.append(card);
        }

        document.getElementById("average").textContent =
            responseCount
                ? `${(responseTotal / responseCount).toFixed(1)} ms`
                : "--";

        document.getElementById("lastUpdate").textContent =
            "Last updated: " + new Date().toLocaleTimeString();

    } catch (error) {

        list.replaceChildren(
            createElement("div", "empty", "Could not load monitors: " + error.message)
        );
    }
}


async function addMonitor(event) {

    event.preventDefault();

    const button = document.getElementById("addButton");

    const name = document.getElementById("name").value.trim();
    const url = document.getElementById("url").value.trim();
    const webhook = document.getElementById("webhook").value.trim();

    if (!name || !url) {
        showToast("Please fill in the required fields.");
        return;
    }

    button.disabled = true;
    button.textContent = "Adding...";

    try {

        await apiFetch(`${API}/monitors`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                url,
                webhook_url: webhook || null
            })
        });

        document.getElementById("addForm").reset();

        showToast("Monitor added successfully.");

        await loadMonitors();

    } catch (error) {

        showToast(error.message);

    } finally {

        button.disabled = false;
        button.textContent = "+ Add monitor";
    }
}


async function deleteMonitor(id) {

    if (!confirm("Are you sure you want to delete this monitor?")) {
        return;
    }

    try {

        await apiFetch(`${API}/monitors/${id}`, {
            method: "DELETE"
        });

        showToast("Monitor deleted.");

        closeDetails();
        await loadMonitors();

    } catch (error) {

        showToast(error.message);
    }
}


async function runManualCheck(id, button) {

    button.disabled = true;
    button.textContent = "Checking...";

    try {

        await apiFetch(`${API}/monitors/${id}/check`, {
            method: "POST"
        });

        showToast("Check completed.");

        await loadMonitors();

    } catch (error) {

        showToast(error.message);

    } finally {

        button.disabled = false;
        button.textContent = "Check";
    }
}


async function showDetails(monitor) {

    const panel = document.getElementById("details");

    panel.classList.add("active");

    document.getElementById("detailName").textContent = monitor.name;
    document.getElementById("detailUrl").textContent = monitor.url;

    document.getElementById("detailUptime").textContent = "--";
    document.getElementById("detailAverage").textContent = "--";
    document.getElementById("detailChecks").textContent = "--";

    try {

        const [stats, history] = await Promise.all([
            apiFetch(`${API}/monitors/${monitor.id}/stats?hours=24`),
            apiFetch(`${API}/monitors/${monitor.id}/history?limit=50`)
        ]);

        document.getElementById("detailUptime").textContent =
            `${stats.uptime_percentage}%`;

        document.getElementById("detailAverage").textContent =
            stats.average_response_time !== null
                ? `${stats.average_response_time} ms`
                : "--";

        document.getElementById("detailChecks").textContent =
            stats.total_checks;

        drawChart(history);

        const historyList = document.getElementById("historyList");
        historyList.replaceChildren();

        if (!history.length) {
            historyList.append(
                createElement("div", "empty", "No history available.")
            );
        }

        for (const item of history) {

            const row = createElement("div", "history-item");

            const left = createElement(
                "span",
                item.is_up ? "green" : "red",
                item.is_up ? "ONLINE" : "OFFLINE"
            );

            const right = createElement(
                "span",
                "muted",
                `${item.response_time_ms ?? "--"} ms · ${
                    item.checked_at
                        ? new Date(item.checked_at).toLocaleString()
                        : "Unknown time"
                }`
            );

            row.append(left, right);
            historyList.append(row);
        }

        panel.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    } catch (error) {

        showToast("Could not load monitor details: " + error.message);
    }
}


function closeDetails() {
    document.getElementById("details").classList.remove("active");
}


function drawChart(history) {

    const canvas = document.getElementById("responseChart");
    const ctx = canvas.getContext("2d");

    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;

    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;

    ctx.scale(ratio, ratio);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    const values = [...history]
        .reverse()
        .map(item => item.response_time_ms);

    if (!values.some(value => value !== null)) {

        ctx.fillStyle = "#8493aa";
        ctx.font = "13px system-ui";
        ctx.fillText("No response time data available", 10, 30);

        return;
    }

    const valid = values.filter(value => value !== null);

    const max = Math.max(...valid, 1) * 1.2;
    const padding = 20;

    ctx.strokeStyle = "#243147";
    ctx.lineWidth = 1;

    for (let i = 0; i < 4; i++) {
        const y = padding + i * (height - padding * 2) / 3;

        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }

    const points = values.map((value, index) => {

        const x = padding +
            index * (width - padding * 2) /
            Math.max(values.length - 1, 1);

        const y = height - padding -
            ((value || 0) / max) * (height - padding * 2);

        return { x, y, value };
    });

    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.beginPath();

    let started = false;

    for (const point of points) {

        if (point.value === null) {
            started = false;
            continue;
        }

        if (!started) {
            ctx.moveTo(point.x, point.y);
            started = true;
        } else {
            ctx.lineTo(point.x, point.y);
        }
    }

    ctx.stroke();
}


document.getElementById("addForm").addEventListener(
    "submit",
    addMonitor
);


loadMonitors();

refreshTimer = setInterval(loadMonitors, 15000);

</script>

</body>
</html>
""")
