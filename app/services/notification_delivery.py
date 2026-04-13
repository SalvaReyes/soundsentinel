from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json
from typing import Any
from urllib import error
from urllib import parse
from urllib import request

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.alert_event import AlertEvent
from app.models.device import Device
from app.models.notification_delivery import NotificationDelivery


def format_telegram_message(device: Device, alert: AlertEvent) -> str:
    return (
        f"SoundSentinel alert\n"
        f"Device: {device.display_name}\n"
        f"Type: {alert.alert_type}\n"
        f"Severity: {alert.severity}\n"
        f"Message: {alert.message}"
    )


def _send_telegram_message(text: str) -> tuple[int, dict[str, Any]]:
    settings = get_settings()
    url = f"{settings.telegram_api_base_url}/bot{settings.telegram_bot_token}/sendMessage"
    payload = parse.urlencode({"chat_id": settings.telegram_chat_id, "text": text}).encode()
    req = request.Request(url, data=payload, method="POST")

    with request.urlopen(req, timeout=settings.notification_request_timeout_seconds) as response:
        response_code = response.getcode()
        response_payload = json.loads(response.read().decode("utf-8"))
        return response_code, response_payload


def deliver_alert_notifications(
    session: Session,
    device: Device,
    alerts: list[AlertEvent],
) -> list[NotificationDelivery]:
    settings = get_settings()
    deliveries: list[NotificationDelivery] = []

    for alert in alerts:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            delivery = NotificationDelivery(
                alert_id=alert.id,
                device_id=device.id,
                channel="telegram",
                recipient=settings.telegram_chat_id or "",
                status="skipped",
                error_message="Telegram is not configured.",
            )
            session.add(delivery)
            deliveries.append(delivery)
            continue

        try:
            response_code, response_payload = _send_telegram_message(
                format_telegram_message(device=device, alert=alert),
            )
            message_id = response_payload.get("result", {}).get("message_id")
            delivery = NotificationDelivery(
                alert_id=alert.id,
                device_id=device.id,
                channel="telegram",
                recipient=settings.telegram_chat_id,
                status="sent",
                response_code=response_code,
                external_message_id=str(message_id) if message_id is not None else None,
                delivered_at=datetime.now(timezone.utc),
            )
        except error.HTTPError as exc:
            delivery = NotificationDelivery(
                alert_id=alert.id,
                device_id=device.id,
                channel="telegram",
                recipient=settings.telegram_chat_id,
                status="failed",
                response_code=exc.code,
                error_message=str(exc),
            )
        except error.URLError as exc:
            delivery = NotificationDelivery(
                alert_id=alert.id,
                device_id=device.id,
                channel="telegram",
                recipient=settings.telegram_chat_id,
                status="failed",
                error_message=str(exc.reason),
            )

        session.add(delivery)
        deliveries.append(delivery)

    return deliveries
