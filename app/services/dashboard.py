from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone

from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.alert_event import AlertEvent
from app.models.audio_sample import AudioSample
from app.models.device import Device
from app.models.notification_delivery import NotificationDelivery


@dataclass
class DeviceStatusView:
    display_name: str
    device_key: str
    status: str
    last_seen_at: str
    latest_rms: str
    latest_peak: str
    sample_count: int
    alert_count: int


@dataclass
class DashboardSnapshot:
    totals: dict
    devices: list[DeviceStatusView]
    recent_samples: list[dict]
    recent_alerts: list[dict]
    recent_deliveries: list[dict]


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "No data yet"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _sensor_status(last_seen_at: datetime | None) -> str:
    if last_seen_at is None:
        return "never_seen"
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)

    settings = get_settings()
    age_seconds = (datetime.now(timezone.utc) - last_seen_at).total_seconds()
    if age_seconds <= settings.sensor_offline_threshold_seconds:
        return "online"
    return "stale"


def build_dashboard_snapshot(session: Session) -> DashboardSnapshot:
    total_devices = session.scalar(select(func.count()).select_from(Device)) or 0
    total_samples = session.scalar(select(func.count()).select_from(AudioSample)) or 0
    total_alerts = session.scalar(select(func.count()).select_from(AlertEvent)) or 0
    total_deliveries = (
        session.scalar(select(func.count()).select_from(NotificationDelivery)) or 0
    )

    devices = list(session.scalars(select(Device).order_by(Device.last_seen_at.desc())))
    latest_samples_by_device: dict[int, AudioSample] = {}
    for sample in session.scalars(select(AudioSample).order_by(AudioSample.measured_at.desc())):
        latest_samples_by_device.setdefault(sample.device_id, sample)

    device_rows: list[DeviceStatusView] = []
    for device in devices:
        latest_sample = latest_samples_by_device.get(device.id)
        sample_count = (
            session.scalar(
                select(func.count()).select_from(AudioSample).where(AudioSample.device_id == device.id),
            )
            or 0
        )
        alert_count = (
            session.scalar(
                select(func.count()).select_from(AlertEvent).where(AlertEvent.device_id == device.id),
            )
            or 0
        )
        device_rows.append(
            DeviceStatusView(
                display_name=device.display_name,
                device_key=device.device_key,
                status=_sensor_status(device.last_seen_at),
                last_seen_at=_format_datetime(device.last_seen_at),
                latest_rms=f"{latest_sample.normalized_rms:.3f}" if latest_sample else "No data",
                latest_peak=f"{latest_sample.normalized_peak:.3f}" if latest_sample else "No data",
                sample_count=sample_count,
                alert_count=alert_count,
            ),
        )

    recent_samples = []
    for sample in session.scalars(
        select(AudioSample).order_by(desc(AudioSample.measured_at)).limit(8)
    ):
        device = session.get(Device, sample.device_id)
        recent_samples.append(
            {
                "device_name": device.display_name if device else f"Device {sample.device_id}",
                "measured_at": _format_datetime(sample.measured_at),
                "normalized_rms": f"{sample.normalized_rms:.3f}",
                "normalized_peak": f"{sample.normalized_peak:.3f}",
                "duration_seconds": f"{sample.duration_seconds:.2f}",
            }
        )

    recent_alerts = []
    for alert in session.scalars(
        select(AlertEvent).order_by(desc(AlertEvent.triggered_at)).limit(8)
    ):
        device = session.get(Device, alert.device_id)
        recent_alerts.append(
            {
                "device_name": device.display_name if device else f"Device {alert.device_id}",
                "triggered_at": _format_datetime(alert.triggered_at),
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
            }
        )

    recent_deliveries = []
    for delivery in session.scalars(
        select(NotificationDelivery).order_by(desc(NotificationDelivery.created_at)).limit(8)
    ):
        alert = session.get(AlertEvent, delivery.alert_id)
        recent_deliveries.append(
            {
                "created_at": _format_datetime(delivery.created_at),
                "channel": delivery.channel,
                "status": delivery.status,
                "recipient": delivery.recipient or "Not configured",
                "alert_type": alert.alert_type if alert else "unknown",
                "error_message": delivery.error_message or "",
            }
        )

    return DashboardSnapshot(
        totals={
            "devices": total_devices,
            "samples": total_samples,
            "alerts": total_alerts,
            "deliveries": total_deliveries,
        },
        devices=device_rows,
        recent_samples=recent_samples,
        recent_alerts=recent_alerts,
        recent_deliveries=recent_deliveries,
    )
