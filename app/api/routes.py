from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import APIRouter
from fastapi import UploadFile
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.config import get_settings
from app.db.session import get_db_session
from app.services.dashboard import build_dashboard_snapshot
from app.services.health import get_liveness_status
from app.services.health import get_readiness_status
from app.services.ingestion import register_audio_ingestion

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    settings = get_settings()
    snapshot = build_dashboard_snapshot(session)
    context = {
        "request": request,
        "app_name": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "snapshot": snapshot,
    }
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/sensor", response_class=HTMLResponse)
async def sensor(request: Request) -> HTMLResponse:
    settings = get_settings()
    context = {
        "request": request,
        "app_name": settings.app_name,
        "environment": settings.environment,
        "version": settings.app_version,
    }
    return templates.TemplateResponse(request, "sensor.html", context)


@router.get("/health")
async def health() -> dict:
    return get_liveness_status()


@router.get("/health/ready")
async def readiness() -> dict:
    return get_readiness_status()


@router.post("/api/v1/audio/ingestions")
async def ingest_audio(
    device_key: str = Form(...),
    captured_at: Optional[str] = Form(None),
    audio_file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
) -> dict:
    ingestion, audio_sample, alerts, deliveries = await register_audio_ingestion(
        session=session,
        device_key=device_key,
        audio_file=audio_file,
        captured_at=captured_at,
    )

    return {
        "status": "accepted",
        "ingestion_id": ingestion.id,
        "device_key": device_key,
        "filename": ingestion.original_filename,
        "content_type": ingestion.content_type,
        "size_bytes": ingestion.size_bytes,
        "sample": {
            "duration_seconds": audio_sample.duration_seconds,
            "sample_rate_hz": audio_sample.sample_rate_hz,
            "channel_count": audio_sample.channel_count,
            "rms_amplitude": audio_sample.rms_amplitude,
            "peak_amplitude": audio_sample.peak_amplitude,
            "normalized_rms": audio_sample.normalized_rms,
            "normalized_peak": audio_sample.normalized_peak,
        },
        "alerts": [
            {
                "id": alert.id,
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
            }
            for alert in alerts
        ],
        "notifications": [
            {
                "id": delivery.id,
                "channel": delivery.channel,
                "status": delivery.status,
                "recipient": delivery.recipient,
                "error_message": delivery.error_message,
            }
            for delivery in deliveries
        ],
    }
