import asyncio
import csv
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .checker import monitor_loop
from .config_loader import (
    add_service,
    import_services,
    load_services,
    parse_uploaded_csv,
    parse_uploaded_json,
    save_services,
)
from .database import Base, SessionLocal, engine, get_db
from .models import ServiceCheck
from .schemas import ServiceCheckOut
from .incident_summary import generate_ai_incident_summary
from fastapi.responses import StreamingResponse
from io import StringIO
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()
SGT = ZoneInfo("Asia/Singapore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    task = asyncio.create_task(monitor_loop(SessionLocal))
    app.state.monitor_task = task
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Service Reliability Monitor", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/services")
def create_service(
    name: str = Form(...),
    url: str = Form(...),
    expected_version: str = Form(...),
    environment: str = Form(...)
):
    try:
        service = add_service(
            {
                "name": name,
                "url": url,
                "expected_version": expected_version,
                "environment": environment
            }
        )
        return {"message": "Service added", "service": service}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/services/import")
async def import_services_file(file: UploadFile = File(...)):
    filename = (file.filename or "").lower()
    content = await file.read()

    try:
        if filename.endswith(".json"):
            services = parse_uploaded_json(content)
        elif filename.endswith(".csv"):
            services = parse_uploaded_csv(content)
        else:
            raise ValueError("Only .json and .csv files are supported")

        added_count = import_services(services)
        return {"message": "Import completed", "added_count": added_count}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/config/services")
def get_configured_services():
    return {"services": load_services()}

@app.get("/api/services/latest")
def get_latest_statuses(db: Session = Depends(get_db)):
    rows = db.query(ServiceCheck).order_by(
        ServiceCheck.checked_at.desc(),
        ServiceCheck.id.desc()
    ).all()

    latest_by_name = {}
    for row in rows:
        if row.service_name not in latest_by_name:
            latest_by_name[row.service_name] = row

    services_list = []
    for row in latest_by_name.values():
        checked = row.checked_at
        if checked:
            # SQLite returns naive datetime; treat it as UTC
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
        services_list.append(
            {
                "service_name": row.service_name,
                "url": row.url,
                "expected_version": row.expected_version,
                "observed_version": row.observed_version,
                "status": row.status,
                "status_code": row.status_code,
                "latency_ms": row.latency_ms,
                "version_drift": row.version_drift,
                "error_message": row.error_message,
                "environment": row.environment,
                "checked_at": checked.isoformat() if checked else None,
            }
        )

    summary = {
        "healthy": sum(1 for r in latest_by_name.values() if r.status == "healthy"),
        "degraded": sum(1 for r in latest_by_name.values() if r.status == "degraded"),
        "down": sum(1 for r in latest_by_name.values() if r.status == "down"),
        "total": len(latest_by_name),
    }

    return {
        "summary": summary,
        "services": services_list,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/services/history/{service_name}", response_model=list[ServiceCheckOut])
def get_service_history(service_name: str, db: Session = Depends(get_db)):
    return (
        db.query(ServiceCheck)
        .filter(ServiceCheck.service_name == service_name)
        .order_by(desc(ServiceCheck.checked_at), desc(ServiceCheck.id))
        .limit(50)
        .all()
    )

@app.get("/api/health")
def healthcheck():
    return {"status": "ok"}

@app.delete("/api/services/{service_name}")
def delete_service(service_name: str):
    services = load_services()
    original_count = len(services)
    services = [s for s in services if s["name"] != service_name]
    
    if len(services) == original_count:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    save_services(services)
    return {"message": f"Service '{service_name}' deleted"}

@app.get("/api/export/checks.csv")
def export_checks_csv(db: Session = Depends(get_db)):
    rows = (
        db.query(ServiceCheck)
        .order_by(ServiceCheck.checked_at.desc(), ServiceCheck.id.desc())
        .all()
    )

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "service_name",
        "environment",
        "url",
        "expected_version",
        "observed_version",
        "status",
        "status_code",
        "latency_ms",
        "version_drift",
        "error_message",
        "checked_at",
    ])

    for row in rows:
        writer.writerow([
            row.id,
            row.service_name,
            row.environment,
            row.url,
            row.expected_version,
            row.observed_version,
            row.status,
            row.status_code,
            row.latency_ms,
            row.version_drift,
            row.error_message,
            row.checked_at,
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=service_checks.csv"},
    )

@app.get("/api/incidents/summary")
def get_incident_summary(db: Session = Depends(get_db)):
    try:
        summary = generate_ai_incident_summary(db, hours=1)
        return {"summary": summary}
    except Exception as exc:
        # important: always return JSON so the frontend can parse it
        return JSONResponse(status_code=500, content={"detail": str(exc)})