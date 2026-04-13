from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.alert_event import AlertEvent
from app.models.audio_sample import AudioSample
from app.models.device import Device


@dataclass
class AlertCandidate:
    alert_type: str
    severity: str
    message: str
    metric_value: float
    threshold_value: float
    window_seconds: int


def _device_recent_samples(session: Session, device_id: int, window_seconds: int) -> list[AudioSample]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    statement = (
        select(AudioSample)
        .where(AudioSample.device_id == device_id, AudioSample.measured_at >= cutoff)
        .order_by(AudioSample.measured_at.desc())
    )
    return list(session.scalars(statement))


def _is_alert_suppressed(session: Session, device_id: int, alert_type: str) -> bool:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.alert_cooldown_seconds)
    statement = (
        select(AlertEvent)
        .where(
            AlertEvent.device_id == device_id,
            AlertEvent.alert_type == alert_type,
            AlertEvent.triggered_at >= cutoff,
        )
        .order_by(desc(AlertEvent.triggered_at))
        .limit(1)
    )
    return session.scalar(statement) is not None


def _build_spike_candidate(sample: AudioSample) -> AlertCandidate | None:
    settings = get_settings()
    if sample.normalized_peak < settings.spike_peak_threshold:
        return None

    return AlertCandidate(
        alert_type="spike_peak",
        severity="high",
        message=(
            f"Peak noise detected at {sample.normalized_peak:.3f}, "
            f"above the spike threshold of {settings.spike_peak_threshold:.3f}."
        ),
        metric_value=sample.normalized_peak,
        threshold_value=settings.spike_peak_threshold,
        window_seconds=0,
    )


def _build_sustained_noise_candidate(session: Session, sample: AudioSample) -> AlertCandidate | None:
    settings = get_settings()
    recent_samples = _device_recent_samples(
        session=session,
        device_id=sample.device_id,
        window_seconds=settings.sustained_noise_window_seconds,
    )
    total_duration = sum(item.duration_seconds for item in recent_samples)
    if total_duration < settings.sustained_noise_window_seconds:
        return None

    average_rms = sum(item.normalized_rms for item in recent_samples) / len(recent_samples)
    if average_rms < settings.sustained_noise_threshold:
        return None

    return AlertCandidate(
        alert_type="sustained_noise",
        severity="medium",
        message=(
            f"Sustained noise detected with average RMS {average_rms:.3f} "
            f"over the last {settings.sustained_noise_window_seconds} seconds."
        ),
        metric_value=average_rms,
        threshold_value=settings.sustained_noise_threshold,
        window_seconds=settings.sustained_noise_window_seconds,
    )


def _build_repeated_peak_candidate(session: Session, sample: AudioSample) -> AlertCandidate | None:
    settings = get_settings()
    recent_samples = _device_recent_samples(
        session=session,
        device_id=sample.device_id,
        window_seconds=settings.repeated_peak_window_seconds,
    )
    peak_count = sum(
        1 for item in recent_samples if item.normalized_peak >= settings.repeated_peak_threshold
    )
    if peak_count < settings.repeated_peak_min_count:
        return None

    return AlertCandidate(
        alert_type="repeated_peaks",
        severity="medium",
        message=(
            f"Repeated peaks detected: {peak_count} peaks above "
            f"{settings.repeated_peak_threshold:.3f} in the last "
            f"{settings.repeated_peak_window_seconds} seconds."
        ),
        metric_value=float(peak_count),
        threshold_value=float(settings.repeated_peak_min_count),
        window_seconds=settings.repeated_peak_window_seconds,
    )


def analyze_sample_behavior(session: Session, device: Device, sample: AudioSample) -> list[AlertEvent]:
    candidates = [
        _build_spike_candidate(sample),
        _build_sustained_noise_candidate(session, sample),
        _build_repeated_peak_candidate(session, sample),
    ]

    alerts: list[AlertEvent] = []
    for candidate in candidates:
        if candidate is None:
            continue
        if _is_alert_suppressed(session, device.id, candidate.alert_type):
            continue

        alert = AlertEvent(
            device_id=device.id,
            sample_id=sample.id,
            alert_type=candidate.alert_type,
            severity=candidate.severity,
            message=candidate.message,
            metric_value=candidate.metric_value,
            threshold_value=candidate.threshold_value,
            window_seconds=candidate.window_seconds,
        )
        session.add(alert)
        alerts.append(alert)

    return alerts
