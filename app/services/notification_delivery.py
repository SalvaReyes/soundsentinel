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
from app.models.notification_recipient import NotificationRecipient


def format_telegram_message(device: Device, alert: AlertEvent) -> str:
    return (
        f"SoundSentinel alert\n"
        f"Device: {device.display_name}\n"
        f"Type: {alert.alert_type}\n"
        f"Severity: {alert.severity}\n"
        f"Message: {alert.message}"
    )


def _send_telegram_message(chat_id: str, text: str) -> tuple[int, dict[str, Any]]:
    settings = get_settings()
    url = f"{settings.telegram_api_base_url}/bot{settings.telegram_bot_token}/sendMessage"
    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = request.Request(url, data=payload, method="POST")

    with request.urlopen(req, timeout=settings.notification_request_timeout_seconds) as response:
        response_code = response.getcode()
        response_payload = json.loads(response.read().decode("utf-8"))
        return response_code, response_payload


def _resolve_recipients(session: Session, settings) -> list[str]:
    recipients = session.query(NotificationRecipient).filter_by(enabled=True).all()
    if recipients:
        return [recipient.chat_id for recipient in recipients]
    if settings.telegram_chat_id:
        return [settings.telegram_chat_id]
    return []


def deliver_alert_notifications(
    session: Session,
    device: Device,
    alerts: list[AlertEvent],
) -> list[NotificationDelivery]:
    settings = get_settings()
    deliveries: list[NotificationDelivery] = []
    recipient_ids = _resolve_recipients(session, settings)

    for alert in alerts:
        if not settings.telegram_bot_token or not recipient_ids:
            delivery = NotificationDelivery(
                alert_id=alert.id,
                device_id=device.id,
                channel="telegram",
                recipient=recipient_ids[0] if recipient_ids else "",
                status="skipped",
                error_message="Telegram is not configured.",
            )
            session.add(delivery)
            deliveries.append(delivery)
            continue

        for chat_id in recipient_ids:
            try:
                response_code, response_payload = _send_telegram_message(
                    chat_id,
                    format_telegram_message(device=device, alert=alert),
                )
                message_id = response_payload.get("result", {}).get("message_id")
                delivery = NotificationDelivery(
                    alert_id=alert.id,
                    device_id=device.id,
                    channel="telegram",
                    recipient=chat_id,
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
                    recipient=chat_id,
                    status="failed",
                    response_code=exc.code,
                    error_message=str(exc),
                )
            except error.URLError as exc:
                delivery = NotificationDelivery(
                    alert_id=alert.id,
                    device_id=device.id,
                    channel="telegram",
                    recipient=chat_id,
                    status="failed",
                    error_message=str(exc.reason),
                )

            session.add(delivery)
            deliveries.append(delivery)

    return deliveries
