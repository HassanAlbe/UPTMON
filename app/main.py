import asyncio
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import engine, Base, SessionLocal, get_db
from models import Monitor, CheckLog
from schemas import MonitorCreate, MonitorOut, CheckLogOut
from checker import check_single_monitor

Base.metadata.create_all(bind=engine)

async def run_all_checks():
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).all()
        tasks = [check_single_monitor(db, m) for m in monitors]
        if tasks:
            await asyncio.gather(*tasks)
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_all_checks, "interval", minutes=1)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Uptime Monitor", lifespan=lifespan)

@app.post("/api/monitors", response_model=MonitorOut)
async def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    monitor = Monitor(
        name=payload.name,
        url=str(payload.url),
        webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    await check_single_monitor(db, monitor)
    return monitor

@app.get("/api/monitors", response_model=List[MonitorOut])
def list_monitors(db: Session = Depends(get_db)):
    return db.query(Monitor).all()

@app.delete("/api/monitors/{monitor_id}")
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor nie istnieje")
    db.delete(monitor)
    db.commit()
    return {"status": "deleted"}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Uptime Monitor</title>
        <style>
            body { font-family: system-ui, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 20px; background: #0f172a; color: #e2e8f0; }
            h1 { color: #38bdf8; }
            form { display: flex; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
            input, button { padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #1e293b; color: white; }
            button { background: #0284c7; border: none; cursor: pointer; font-weight: bold; }
            .card { background: #1e293b; padding: 16px; border-radius: 8px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid #22c55e; }
            .card.down { border-left-color: #ef4444; }
            .badge { padding: 4px 10px; border-radius: 99px; font-size: 12px; font-weight: bold; }
            .up { background: #14532d; color: #4ade80; }
            .down-badge { background: #7f1d1d; color: #f87171; }
            .del { background: #dc2626; margin-left: 10px; padding: 6px 10px; font-size: 12px; }
        </style>
    </head>
    <body>
        <h1>Uptime Monitor</h1>
        <form id="addForm">
            <input type="text" id="name" placeholder="Nazwa (np. Google)" required>
            <input type="url" id="url" placeholder="https://google.com" required>
            <input type="url" id="webhook" placeholder="Webhook URL (opcjonalnie)">
            <button type="submit">Dodaj monitor</button>
        </form>
        <div id="list">Ładowanie...</div>
        <script>
            async function loadMonitors() {
                const res = await fetch('/api/monitors');
                const data = await res.json();
                document.getElementById('list').innerHTML = data.map(m => `
                    <div class="card ${m.is_up ? '' : 'down'}">
                        <div>
                            <strong>${m.name}</strong> — <a href="${m.url}" target="_blank" style="color:#94a3b8">${m.url}</a>
                        </div>
                        <div>
                            <span class="badge ${m.is_up ? 'up' : 'down-badge'}">${m.is_up ? 'ONLINE' : 'OFFLINE'}</span>
                            <button class="del" onclick="delMonitor(${m.id})">Usuń</button>
                        </div>
                    </div>
                `).join('') || '<p>Brak monitorów.</p>';
            }
            document.getElementById('addForm').onsubmit = async (e) => {
                e.preventDefault();
                await fetch('/api/monitors', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: document.getElementById('name').value,
                        url: document.getElementById('url').value,
                        webhook_url: document.getElementById('webhook').value || null
                    })
                });
                e.target.reset();
                loadMonitors();
            };
            async function delMonitor(id) {
                await fetch('/api/monitors/' + id, { method: 'DELETE' });
                loadMonitors();
            }
            loadMonitors();
            setInterval(loadMonitors, 15000);
        </script>
    </body>
    </html>
    """