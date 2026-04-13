from datetime import datetime
from datetime import timezone
import re
from typing import Optional

from fastapi import HTTPException
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.alert_event import AlertEvent
from app.models.audio_ingestion import AudioIngestion
from app.models.audio_sample import AudioSample
from app.models.device import Device
from app.models.notification_delivery import NotificationDelivery
from app.services.audio_processing import ComputedAudioMetrics
from app.services.audio_processing import compute_wav_metrics
from app.services.behavior_analysis import analyze_sample_behavior
from app.services.notification_delivery import deliver_alert_notifications

ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
}


def normalize_device_key(device_key: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", device_key.strip().lower()).strip("-")
    if not normalized:
        raise HTTPException(status_code=400, detail="Device key must not be empty.")
    return normalized


def parse_captured_at(captured_at: Optional[str]) -> Optional[datetime]:
    if not captured_at:
        return None

    normalized_value = captured_at.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="captured_at must be a valid ISO 8601 datetime.",
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def validate_audio_upload(audio_file: UploadFile, payload_size: int) -> None:
    settings = get_settings()

    if audio_file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio type. Use wav, mp3, mp4, webm, or ogg audio.",
        )

    if payload_size == 0:
        raise HTTPException(status_code=400, detail="Audio upload is empty.")

    if payload_size > settings.max_audio_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                "Audio upload is too large. "
                f"Maximum allowed size is {settings.max_audio_upload_bytes} bytes."
            ),
        )


async def register_audio_ingestion(
    session: Session,
    device_key: str,
    audio_file: UploadFile,
    captured_at: Optional[str] = None,
) -> tuple[AudioIngestion, AudioSample, list[AlertEvent], list[NotificationDelivery]]:
    normalized_key = normalize_device_key(device_key)
    captured_at_value = parse_captured_at(captured_at)
    payload = await audio_file.read()

    validate_audio_upload(audio_file=audio_file, payload_size=len(payload))
    computed_metrics: ComputedAudioMetrics = compute_wav_metrics(payload)

    device = session.scalar(select(Device).where(Device.device_key == normalized_key))
    if device is None:
        device = Device(
            device_key=normalized_key,
            display_name=normalized_key,
        )
        session.add(device)
        session.flush()

    device.last_seen_at = datetime.now(timezone.utc)

    ingestion = AudioIngestion(
        device_id=device.id,
        captured_at=captured_at_value,
        original_filename=audio_file.filename or "unnamed-audio",
        content_type=audio_file.content_type or "application/octet-stream",
        size_bytes=len(payload),
    )
    session.add(ingestion)
    session.flush()

    audio_sample = AudioSample(
        ingestion_id=ingestion.id,
        device_id=device.id,
        duration_seconds=computed_metrics.duration_seconds,
        sample_rate_hz=computed_metrics.sample_rate_hz,
        channel_count=computed_metrics.channel_count,
        rms_amplitude=computed_metrics.rms_amplitude,
        peak_amplitude=computed_metrics.peak_amplitude,
        normalized_rms=computed_metrics.normalized_rms,
        normalized_peak=computed_metrics.normalized_peak,
    )
    session.add(audio_sample)
    session.flush()

    alerts: list[AlertEvent] = analyze_sample_behavior(
        session=session,
        device=device,
        sample=audio_sample,
    )
    session.flush()
    deliveries: list[NotificationDelivery] = deliver_alert_notifications(
        session=session,
        device=device,
        alerts=alerts,
    )
    session.commit()
    session.refresh(ingestion)
    session.refresh(audio_sample)
    for alert in alerts:
        session.refresh(alert)
    for delivery in deliveries:
        session.refresh(delivery)

    return ingestion, audio_sample, alerts, deliveries
